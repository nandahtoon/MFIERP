# SPDX-License-Identifier: LGPL-3.0-or-later
import json
import hashlib
import re

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from ..services import datatables, workspace
from ..services.fineract import FineractError
from ..services.operations import RESOURCES
from ..models.mfierp_upload import upload_bytes


TYPES = [(key, label) for key, label in [
    ("string", "Text / Option"), ("integer", "Integer"), ("number", "Amount / Rate"),
    ("boolean", "Yes / No"), ("date", "Date"), ("object", "Details"), ("array", "Rows"), ("binary", "File"), ("secret", "Protected Secret"),
]]


class MfierpRequest(models.TransientModel):
    _name = "mfierp.request"
    _description = "Native Fineract Workflow Form"
    _check_company_auto = True

    name = fields.Char(compute="_compute_contract_details")
    capability_id = fields.Many2one("mfierp.capability")
    datatable_id = fields.Many2one("mfierp.datatable", check_company=True)
    datatable_action = fields.Selection([("read", "Read Entries"), ("create", "Create Entry"),
        ("update", "Update Entry"), ("delete", "Delete Entry")], default="read", required=True)
    backend_id = fields.Many2one("mfierp.backend", string="Fineract Connection", required=True, check_company=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    target_id = fields.Many2one("mfierp.record", check_company=True, readonly=True)
    method = fields.Char(compute="_compute_contract_details")
    instructions = fields.Text(compute="_compute_contract_details")
    input_ids = fields.One2many("mfierp.input", "request_id", string="Workflow Fields")
    root_input_ids = fields.One2many("mfierp.input", "request_id", string="Workflow Fields", domain=[("parent_id", "=", False)])
    initialized = fields.Boolean(readonly=True)
    contract_digest = fields.Char(readonly=True)
    result_text = fields.Text(readonly=True)
    result_html = fields.Html(readonly=True, sanitize=True)
    result_status = fields.Char(readonly=True)
    command_id = fields.Many2one("mfierp.command", readonly=True)
    output_mode = fields.Selection([("json", "Table / Structured Data"), ("file", "Download File")], default="json", required=True)
    download_data = fields.Binary(readonly=True, attachment=False)
    download_name = fields.Char(readonly=True)

    @api.depends("capability_id", "datatable_id", "datatable_action")
    def _compute_contract_details(self):
        for request in self:
            if request.datatable_id:
                request.name = _("%s: %s", request.datatable_id.name, dict(self._fields["datatable_action"].selection)[request.datatable_action])
                request.method = datatables.ACTIONS.get(request.datatable_action)
                request.instructions = _("Fields come from this connection's registered table metadata. Enter the parent record ID. Multi-row updates and deletion also require the entry ID. Optional fields can be omitted; clearing a field to NULL is not supported. Fineract owns values and validation. Writes require independent approval.")
            else:
                request.name = request.capability_id.name
                request.method = request.capability_id.method
                request.instructions = request.capability_id.description

    @api.constrains("capability_id", "datatable_id", "backend_id")
    def _check_contract(self):
        for request in self:
            if bool(request.capability_id) == bool(request.datatable_id):
                raise UserError(_("Choose exactly one source workflow or registered data table."))
            if request.datatable_id and request.datatable_id.backend_id != request.backend_id:
                raise UserError(_("The data table belongs to another connection."))

    def _specification(self):
        if self.datatable_id:
            return self.datatable_id._specification(self.datatable_action)
        return workspace.specification(self.capability_id.key)

    def _contract_digest(self):
        if self.datatable_id:
            return self.datatable_id._contract_digest(self.datatable_action)
        return workspace.contract_digest(self.capability_id.key)

    def _build_request(self, envelope, *, allow_staged=False):
        if self.datatable_id:
            return self.datatable_id._build_request(self.datatable_action, envelope)
        return workspace.build_request(self.capability_id.key, envelope, allow_staged=allow_staged)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            for vals in vals_list:
                if any(vals.get(key) for key in ("initialized", "contract_digest", "result_text", "result_html", "result_status", "command_id", "download_data", "download_name")):
                    raise AccessError(_("Workflow outcomes cannot be supplied by the client."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and {"initialized", "contract_digest", "result_text", "result_html", "result_status", "command_id", "download_data", "download_name"} & vals.keys():
            raise AccessError(_("Workflow outcomes are maintained by authorized actions."))
        if not self.env.su and {"capability_id", "datatable_id", "datatable_action", "backend_id", "company_id", "target_id"} & vals.keys() and any(self.mapped("initialized")):
            raise UserError(_("Start a new workflow form to change its connection, company or operation."))
        return super().write(vals)

    def _assert_access(self):
        self.ensure_one()
        self.check_access("read")
        self._check_contract()
        spec = self.datatable_id._assert_role(self.datatable_action) if self.datatable_id else self.capability_id._assert_role()
        if self.datatable_id and self.output_mode != "json":
            raise UserError(_("Use the bounded native table preview for registered data table entries."))
        self.backend_id.check_access("read")
        if not self.backend_id.active or self.backend_id.company_id != self.company_id or self.company_id not in self.env.companies:
            raise AccessError(_("Select an active connection in an allowed company."))
        if self.target_id:
            self.target_id.check_access("read")
            if self.target_id.backend_id != self.backend_id:
                raise UserError(_("The workflow target belongs to another connection."))
            if spec.get("context_resource") and spec["context_resource"] != RESOURCES[self.target_id.kind][0]:
                raise UserError(_("The target record does not match this workflow's entity type."))
        return spec

    def _node(self, key, schema, location, parent=None, required=False, array_item=False, depth=0):
        if depth > 8 or len(self.input_ids) >= 2000:
            raise UserError(_("This form exceeds the reviewed structure limit."))
        schema = workspace.resolve(schema)
        kind = workspace.value_type(schema, key)
        if kind not in dict(TYPES):
            raise UserError(_("This field requires a dedicated typed contract."))
        label = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", key).replace("_", " ").strip().capitalize()
        label = schema.get("title", label)[:250]
        singleton = schema.get("enum", [])
        locked = key in {"dateFormat", "locale"} or len(singleton) == 1
        vals = {"request_id": self.id, "parent_id": parent.id if parent else False,
            "key": key, "label": label, "location": location, "kind": kind, "required": required,
            "included": required or locked or (location == "body" and not parent), "locked": locked, "array_item": array_item,
            "schema_json": schema, "description": schema.get("description"),
            "options_text": ", ".join(map(str, schema.get("enum", [])))}
        if locked:
            value = singleton[0] if len(singleton) == 1 else "yyyy-MM-dd" if key == "dateFormat" else "en"
            field = {"integer": "integer_value", "number": "number_value", "boolean": "boolean_value"}.get(kind, "text_value")
            vals[field] = value
        if location == "query" and key in {"limit", "offset"}:
            vals.update(included=True, integer_value=200 if key == "limit" else 0)
        if location == "path" and self.target_id:
            parts = self._specification()["path"].strip("/").split("/")[1:]
            if parts[0] == RESOURCES[self.target_id.kind][0] and len(parts) > 1 and parts[1] == "{" + key + "}":
                if kind == "integer":
                    vals["integer_value"] = self.target_id.remote_id
                elif kind == "string":
                    vals["text_value"] = str(self.target_id.remote_id)
        if self.target_id:
            spec = self._specification()
            if spec.get("context_resource") == RESOURCES[self.target_id.kind][0] and spec.get("context_fields", {}).get(key) == location:
                if kind == "integer":
                    vals.update(included=True, integer_value=self.target_id.remote_id)
                elif kind == "string":
                    vals.update(included=True, text_value=str(self.target_id.remote_id))
        node = self.env["mfierp.input"].sudo().create(vals)
        if kind == "object":
            for name, child in schema.get("properties", {}).items():
                if not child.get("readOnly"):
                    self._node(name, child, location, node, name in schema.get("required", []), depth=depth + 1)
        return node

    def action_load(self):
        spec = self._assert_access()
        if self.initialized:
            raise UserError(_("This form is already initialized."))
        for param in spec["parameters"]:
            self._node(param["name"], param["schema"], param["in"], required=param.get("required", False))
        if spec["body"] is not None:
            self._node("details", spec["body"], "body", required=spec["body_required"])
        self.sudo().write({"initialized": True, "contract_digest": self._contract_digest()})
        return True

    def _envelope(self):
        if not self.initialized:
            raise UserError(_("Load the workflow fields first."))
        if self.contract_digest != self._contract_digest():
            raise UserError(_("The source contract changed. Open a new workflow form before submitting or reading."))
        envelope = {"contract_digest": self.contract_digest, "path": {}, "query": {}, "body": None}
        for node in self.input_ids.filtered(lambda line: not line.parent_id):
            if node.included or node.required:
                if node.location == "body":
                    envelope["body"] = node._value()
                else:
                    envelope[node.location][node.key] = node._value()
        try:
            self._build_request(envelope, allow_staged=True)
        except (ValueError, TypeError) as exc:
            raise UserError(str(exc)) from exc
        return envelope

    def action_execute(self):
        spec = self._assert_access()
        envelope = self._envelope()
        if spec["method"] != "GET":
            if self.command_id:
                raise UserError(_("This form has already been submitted. Open its command for review."))
            if self.datatable_id:
                command = self.env["mfierp.command"]._enqueue_datatable(self.backend_id, self.datatable_id, self.datatable_action, envelope)
            else:
                command = self.env["mfierp.command"]._enqueue_workspace(self.backend_id, self.capability_id, envelope, request=self)
            self.sudo().write({"command_id": command.id})
            return {"id": self.env.ref("mfierp.mfierp_command_action").id, "type": "ir.actions.act_window",
                "res_model": "mfierp.command", "res_id": command.id, "view_mode": "form", "target": "current"}
        method, path, params, body = self._build_request(envelope)
        try:
            client = self.backend_id._client()
            if self.datatable_id:
                self.datatable_id._verify_metadata(client)
            result = client.request(method, path, params=params, payload=body,
                binary=self.output_mode == "file", api_version=spec.get("api_version", "v1"))
            if self.datatable_id:
                result = datatables.project_rows(result, self.datatable_id.sudo().metadata_json)
        except (FineractError, UserError, ValueError) as exc:
            self.sudo().write({"result_status": str(exc), "result_text": False, "result_html": False, "download_data": False})
            return True
        if self.output_mode == "file":
            self.sudo().write({"download_data": result["data"], "download_name": "fineract-download.bin",
                "result_status": _("Fineract file read completed."), "result_text": False, "result_html": False})
            return {"type": "ir.actions.act_url", "url": f"/web/content?model=mfierp.request&id={self.id}&field=download_data&filename_field=download_name&download=true", "target": "download"}
        rows = result if isinstance(result, list) else result.get("pageItems", []) if isinstance(result, dict) else []
        table = False
        if rows and all(isinstance(row, dict) for row in rows):
            columns = list(dict.fromkeys(key for row in rows[:200] for key in row))[:15]
            header = Markup("").join(Markup("<th>%s</th>") % escape(key) for key in columns)
            body_html = Markup("").join(Markup("<tr>%s</tr>") % Markup("").join(
                Markup("<td>%s</td>") % escape(str(row.get(key, ""))[:500]) for key in columns) for row in rows[:200])
            table = Markup('<table class="table table-striped"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>') % (header, body_html)
        rendered = json.dumps(result, indent=2, ensure_ascii=False)
        self.sudo().write({"result_status": _("Fineract read completed. Table preview is limited to 200 rows; text preview to 200,000 characters."),
            "result_text": rendered[:200000], "result_html": table})
        return True


class MfierpInput(models.TransientModel):
    _name = "mfierp.input"
    _description = "Typed Fineract Workflow Field"
    _order = "id"
    _rec_name = "label"

    request_id = fields.Many2one("mfierp.request", required=True, readonly=True, ondelete="cascade")
    parent_id = fields.Many2one("mfierp.input", readonly=True, ondelete="cascade")
    child_ids = fields.One2many("mfierp.input", "parent_id")
    company_id = fields.Many2one(related="request_id.company_id")
    key = fields.Char(required=True, readonly=True)
    label = fields.Char(readonly=True)
    location = fields.Selection([("path", "Record"), ("query", "Filter / Option"), ("body", "Details")], readonly=True)
    kind = fields.Selection(TYPES, required=True, readonly=True)
    required = fields.Boolean(readonly=True)
    included = fields.Boolean(string="Include")
    locked = fields.Boolean(readonly=True)
    array_item = fields.Boolean(readonly=True)
    schema_json = fields.Json(readonly=True, groups="mfierp.group_manager")
    description = fields.Text(readonly=True)
    options_text = fields.Char(string="Allowed Options", readonly=True)
    value_summary = fields.Char(compute="_compute_value_summary")
    text_value = fields.Char(string="Text / Option")
    integer_value = fields.Integer(string="Integer")
    number_value = fields.Float(string="Amount / Rate", digits=(20, 8))
    boolean_value = fields.Boolean(string="Yes / No")
    date_value = fields.Date(string="Date")
    binary_value = fields.Binary(string="File", attachment=False)
    binary_name = fields.Char(string="File Name")
    secret_reference = fields.Char(string="Deployment Secret Reference", help="Name of a dedicated MFIERP_WORKFLOW_SECRET_ variable. Never enter its value here. Infrastructure and connection credentials cannot be selected.")

    @api.depends("text_value", "integer_value", "number_value", "boolean_value", "date_value", "child_ids", "included")
    def _compute_value_summary(self):
        for line in self:
            if line.kind in {"array", "object"}:
                line.value_summary = _("%s fields / rows", len(line.child_ids))
            elif line.kind == "secret":
                line.value_summary = line.secret_reference or _("No secret reference selected")
            elif line.kind == "binary":
                line.value_summary = line.binary_name or _("No file selected")
            elif line.included or line.required:
                line.value_summary = str(line._value())
            else:
                line.value_summary = _("Not included")

    @api.onchange("text_value", "integer_value", "number_value", "boolean_value", "date_value", "binary_value", "secret_reference")
    def _onchange_value(self):
        if not self.locked and self.kind not in {"array", "object"}:
            self.included = True

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_("Workflow fields must be created from the reviewed contract."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            if vals.keys() - {"included", "text_value", "integer_value", "number_value", "boolean_value", "date_value", "binary_value", "binary_name", "secret_reference"}:
                raise AccessError(_("The workflow field definition is immutable."))
            if any(self.mapped("locked")):
                raise AccessError(_("This workflow constant cannot be changed."))
            for line in self:
                line.request_id._assert_access()
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            for line in self:
                line.request_id._assert_access()
                if not line.array_item:
                    raise AccessError(_("Declared workflow fields cannot be removed."))
        return super().unlink()

    def _value(self):
        self.ensure_one()
        if self.kind == "secret":
            try:
                return workspace.bind_secret(self.secret_reference,
                    f"{self.request_id.backend_id.id}:{self.request_id.capability_id.key}:{self.request_id.id}:{self.key}")
            except ValueError as exc:
                raise UserError(str(exc)) from exc
        if self.kind == "binary":
            raw = upload_bytes(self.binary_value)
            name = (self.binary_name or self.binary_value.filename or "upload.bin").replace("\\", "/").rsplit("/", 1)[-1]
            if not name or any(char in name for char in "\r\n"):
                raise UserError(_("Use a valid upload file name."))
            return {"storage": "staged", "id": self.id, "sha256": hashlib.sha256(raw).hexdigest(), "name": name}
        if self.kind == "object":
            return {child.key: child._value() for child in self.child_ids if child.included or child.required or child.locked}
        if self.kind == "array":
            return [child._value() for child in self.child_ids]
        if self.key in {"dateFormat", "locale"}:
            return "yyyy-MM-dd" if self.key == "dateFormat" else "en"
        return {"string": self.text_value or "", "integer": self.integer_value, "number": self.number_value,
            "boolean": self.boolean_value, "date": fields.Date.to_string(self.date_value) if self.date_value else ""}[self.kind]

    def action_details(self):
        self.ensure_one()
        self.request_id._assert_access()
        return {"type": "ir.actions.act_window", "name": self.label, "res_model": self._name,
            "res_id": self.id, "view_mode": "form", "target": "new"}

    def action_add_item(self):
        self.ensure_one()
        self.request_id._assert_access()
        if self.kind != "array" or len(self.child_ids) >= 100:
            raise UserError(_("Choose an array with fewer than 100 items."))
        schema = workspace.resolve(self.sudo().schema_json)
        node = self.request_id._node(str(len(self.child_ids) + 1), schema["items"], self.location,
            self, required=True, array_item=True)
        self.sudo().write({"included": True})
        return node.action_details()
