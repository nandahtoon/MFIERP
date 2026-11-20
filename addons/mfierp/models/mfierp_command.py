# SPDX-License-Identifier: LGPL-3.0-or-later
import hashlib
import json
import uuid
import base64
from html import escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import BinaryBytes

from ..services.fineract import FineractError
from ..services.operations import OPERATIONS, build_request
from ..services import datatables, workspace
from ..services.collection_sheet import project_preview
from .mfierp_upload import upload_bytes


class MfierpCommand(models.Model):
    _name = "mfierp.command"
    _description = "Fineract Maker Checker Command"
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(readonly=True, required=True)
    backend_id = fields.Many2one("mfierp.backend", string="Connection", required=True, readonly=True, ondelete="restrict", check_company=True)
    company_id = fields.Many2one(related="backend_id.company_id", store=True, index=True)
    operation = fields.Selection([(key, item[0]) for key, item in OPERATIONS.items()] + [("workspace", "Extended Fineract Workflow")], readonly=True, required=True)
    capability_id = fields.Many2one("mfierp.capability", readonly=True, ondelete="restrict")
    datatable_id = fields.Many2one("mfierp.datatable", readonly=True, ondelete="restrict", check_company=True)
    datatable_action = fields.Selection([("create", "Create Entry"), ("update", "Update Entry"), ("delete", "Delete Entry")], readonly=True)
    upload_ids = fields.One2many("mfierp.upload", "command_id", readonly=True)
    target_id = fields.Many2one("mfierp.record", readonly=True, ondelete="restrict", check_company=True)
    remote_target_id = fields.Integer(readonly=True)
    payload = fields.Json(readonly=True)
    payload_preview = fields.Text(string="Request Details", compute="_compute_payload_preview")
    payload_digest = fields.Char(readonly=True)
    idempotency_key = fields.Char(readonly=True, required=True, index=True)
    state = fields.Selection([
        ("pending", "Awaiting Approval"), ("approved", "Approved"), ("dispatching", "Dispatching"),
        ("done", "Confirmed"), ("remote_pending", "Remote Verification Pending"),
        ("rejected", "Rejected"), ("failed", "Rejected by Fineract"), ("uncertain", "Reconciliation Required"),
    ], default="pending", readonly=True, required=True, index=True)
    maker_id = fields.Many2one("res.users", readonly=True, required=True)
    checker_id = fields.Many2one("res.users", readonly=True)
    approved_at = fields.Datetime(readonly=True)
    dispatched_at = fields.Datetime(readonly=True)
    completed_at = fields.Datetime(readonly=True)
    result_resource_id = fields.Integer(readonly=True)
    result_subresource_id = fields.Integer(readonly=True, string="Fineract Subresource ID")
    result_command_id = fields.Integer(readonly=True)
    status_message = fields.Char(readonly=True)
    preview_data = fields.Json(readonly=True)
    preview_digest = fields.Char(readonly=True)
    preview_purged_at = fields.Datetime(readonly=True)
    preview_html = fields.Html(compute="_compute_preview_html", sanitize=True)
    resolution_note = fields.Text(readonly=True)
    resolved_by_id = fields.Many2one("res.users", readonly=True)

    _key_unique = models.Constraint("UNIQUE(idempotency_key)", "Command idempotency keys must be unique.")

    @api.depends("preview_data")
    def _compute_preview_html(self):
        for command in self:
            data = command.preview_data
            if not data:
                command.preview_html = False
                continue
            keys = ["client", "kind", "remote_id", "product", "currency", "due", "charges"]
            headings = [_("Client"), _("Account Type"), _("Remote ID"), _("Product"), _("Currency"), _("Due (Remote)"), _("Charges (Remote)")]
            header = "".join("<th>" + escape(title) + "</th>" for title in headings)
            rows = "".join("<tr>" + "".join("<td>" + escape("—" if row.get(key) is None else str(row[key])) + "</td>" for key in keys) + "</tr>" for row in data["rows"])
            note = _("Amounts are copied from Fineract. No totals are calculated or payments posted by this preview.")
            if not data["rows"]:
                note += " " + _("No loan or savings rows were included in this preview.")
            if data["truncated"]:
                note += " " + _("Preview limit reached; narrow the office or staff selection.")
            options = "; ".join(f"{row['id']}: {row['name']}" for row in data["payment_types"])
            if options:
                options = _("Payment types: ") + options
            command.preview_html = f'<p>{escape(note)}</p><table class="table table-striped"><thead><tr>{header}</tr></thead><tbody>{rows}</tbody></table><p>{escape(options)}</p>'

    @api.model
    def _cron_purge_previews(self):
        cutoff = fields.Datetime.subtract(fields.Datetime.now(), days=7)
        self.sudo().search([("preview_digest", "!=", False), ("preview_purged_at", "=", False),
            ("completed_at", "<", cutoff), ("state", "=", "done")], limit=100).write({
                "preview_data": False, "preview_purged_at": fields.Datetime.now()})

    @api.depends("payload")
    def _compute_payload_preview(self):
        for command in self:
            command.payload_preview = json.dumps(command.payload or {}, indent=2, sort_keys=True, ensure_ascii=False)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_("Use the operation form to submit a command."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            raise AccessError(_("Commands are immutable. Use their authorized workflow actions."))
        return super().write(vals)

    def unlink(self):
        raise AccessError(_("Commands are retained as audit records and cannot be deleted."))

    @api.model
    def _enqueue(self, backend, operation, payload, target=None):
        if not self.env.user.has_group("mfierp.group_operator"):
            raise AccessError(_("An MFIERP operator role is required."))
        backend.check_access("read")
        if backend.company_id not in self.env.companies or not backend.active:
            raise AccessError(_("Choose an active connection in an allowed company."))
        remote_id = 0
        if target:
            target.check_access("read")
            if target.backend_id != backend or target.kind != OPERATIONS[operation][1]:
                raise UserError(_("The target does not match the connection and operation."))
            remote_id = target.remote_id
        key = str(uuid.uuid4())
        payload = dict(payload)
        if operation.startswith("create_") and not payload.get("externalId"):
            payload["externalId"] = f"MFIERP-{key}"
        try:
            build_request(operation, remote_id, payload)
        except ValueError as exc:
            raise UserError(str(exc)) from exc
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return self.sudo().create({"name": OPERATIONS[operation][0], "backend_id": backend.id,
            "operation": operation, "target_id": target.id if target else False,
            "remote_target_id": remote_id, "payload": payload,
            "payload_digest": hashlib.sha256(canonical.encode()).hexdigest(),
            "idempotency_key": key, "maker_id": self.env.uid})

    def _lock(self):
        self.ensure_one()
        self.check_access("read")
        self.env.cr.execute("SELECT id FROM mfierp_command WHERE id = %s FOR UPDATE", [self.id])
        self.invalidate_recordset()

    @api.model
    def _enqueue_workspace(self, backend, capability, envelope, request=None):
        spec = capability._assert_role()
        if spec["method"] == "GET":
            raise UserError(_("Read workflows do not create financial commands."))
        backend.check_access("read")
        if not backend.active or backend.company_id not in self.env.companies:
            raise AccessError(_("Choose an active connection in an allowed company."))
        try:
            workspace.build_request(capability.key, envelope, allow_staged=True)
        except (TypeError, ValueError) as exc:
            raise UserError(str(exc)) from exc
        envelope = json.loads(json.dumps(envelope))
        uploads = self.env["mfierp.upload"]

        def capture(marker, schema):
            nonlocal uploads
            if not request or marker["storage"] != "staged":
                raise UserError(_("Uploads must originate in this workflow's protected form."))
            request._assert_access()
            if request.backend_id != backend or request.capability_id != capability:
                raise UserError(_("Upload form does not match the reviewed operation."))
            node = self.env["mfierp.input"].browse(marker["id"])
            node.check_access("read")
            if node.request_id != request or node.kind != "binary":
                raise AccessError(_("Upload belongs to another workflow."))
            raw = upload_bytes(node.binary_value)
            if hashlib.sha256(raw).hexdigest() != marker["sha256"]:
                raise UserError(_("Upload changed while the request was prepared."))
            upload = self.env["mfierp.upload"].sudo().create({"name": marker["name"], "backend_id": backend.id,
                "data": BinaryBytes(raw, filename=marker["name"]), "sha256": marker["sha256"]})
            uploads |= upload
            return {**marker, "storage": "command", "id": upload.id}

        if spec["body"] is not None and envelope["body"] is not None:
            envelope["body"] = workspace.map_uploads(envelope["body"], spec["body"], capture)
        workspace.build_request(capability.key, envelope)
        canonical = json.dumps(envelope, sort_keys=True, separators=(",", ":"))
        command = self.sudo().create({"name": capability.name, "backend_id": backend.id, "capability_id": capability.id,
            "operation": "workspace", "payload": envelope, "payload_digest": hashlib.sha256(canonical.encode()).hexdigest(),
            "idempotency_key": str(uuid.uuid4()), "maker_id": self.env.uid})
        uploads.sudo().write({"command_id": command.id})
        return command

    @api.model
    def _enqueue_datatable(self, backend, table, action, envelope):
        spec = table._assert_role(action)
        if spec["method"] == "GET" or backend != table.backend_id:
            raise UserError(_("Choose a write action and the data table's own connection."))
        try:
            table._build_request(action, envelope)
        except (TypeError, ValueError) as exc:
            raise UserError(str(exc)) from exc
        canonical = json.dumps(envelope, sort_keys=True, separators=(",", ":"))
        return self.sudo().create({"name": _("%s: %s", table.name, action), "backend_id": backend.id,
            "datatable_id": table.id, "datatable_action": action, "operation": "workspace", "payload": json.loads(canonical),
            "payload_digest": hashlib.sha256(canonical.encode()).hexdigest(),
            "idempotency_key": str(uuid.uuid4()), "maker_id": self.env.uid})

    def _workspace_specification(self):
        if bool(self.capability_id) == bool(self.datatable_id):
            raise ValueError("Exactly one workflow contract is required.")
        if self.datatable_id:
            if self.datatable_id.backend_id != self.backend_id:
                raise ValueError("Data table connection does not match the command.")
            return self.datatable_id._specification(self.datatable_action)
        return workspace.specification(self.capability_id.key)

    def _workspace_request(self):
        self._workspace_specification()
        if self.datatable_id:
            return self.datatable_id._build_request(self.datatable_action, self.payload)
        return workspace.build_request(self.capability_id.key, self.payload)

    def _workspace_body(self, body):
        spec = self._workspace_specification()
        multipart = spec.get("media_type") == "multipart/form-data"

        def restore(marker, schema):
            upload = self.env["mfierp.upload"].sudo().browse(marker["id"])
            raw = upload._verified_bytes(self, marker)
            return (marker["name"], raw, "application/octet-stream") if multipart else base64.b64encode(raw).decode("ascii")

        if spec["body"] is not None and body is not None:
            body = workspace.map_secrets(body, spec["body"])
            body = workspace.map_uploads(body, spec["body"], restore)
        if not multipart:
            return body, None
        if not isinstance(body, dict):
            raise UserError(_("Multipart uploads require named form fields."))
        files, values = [], {}
        for name, value in body.items():
            if isinstance(value, tuple):
                files.append((name, value))
            elif isinstance(value, list) and value and all(isinstance(item, tuple) for item in value):
                files.extend((name, item) for item in value)
            else:
                values[name] = json.dumps(value) if isinstance(value, (dict, list, bool)) else str(value)
        if not files:
            raise UserError(_("Select the file required by this upload workflow."))
        return values, files

    def action_approve(self):
        self._lock()
        if not self.env.user.has_group("mfierp.group_checker"):
            raise AccessError(_("An MFIERP checker role is required."))
        if self._requires_administrator() and not self.env.user.has_group("mfierp.group_manager"):
            raise AccessError(_("An independent MFIERP administrator must review this administration workflow."))
        if self.maker_id == self.env.user:
            raise UserError(_("A different person must approve this command."))
        if self.state != "pending":
            raise UserError(_("Only pending commands can be approved."))
        self.sudo().write({"state": "approved", "checker_id": self.env.uid, "approved_at": fields.Datetime.now()})
        return True

    def action_reject(self):
        self._lock()
        if not self.env.user.has_group("mfierp.group_checker") or self.maker_id == self.env.user:
            raise AccessError(_("A different checker must reject the command."))
        if self._requires_administrator() and not self.env.user.has_group("mfierp.group_manager"):
            raise AccessError(_("An independent MFIERP administrator must review this administration workflow."))
        if self.state != "pending":
            raise UserError(_("Only pending commands can be rejected."))
        self.sudo().write({"state": "rejected", "checker_id": self.env.uid, "completed_at": fields.Datetime.now()})
        return True

    def _requires_administrator(self):
        self.ensure_one()
        return self.capability_id.admin_only or self.datatable_id.application_table in datatables.ADMIN_APPLICATIONS

    def _requires_reconciliation_resource(self):
        """Only source-declared resource-less operations can confirm without an ID."""
        self.ensure_one()
        if self.operation == "workspace" and self.capability_id:
            try:
                spec = workspace.specification(self.capability_id.key)
            except ValueError:
                return True
            if spec["admin_only"] and spec.get("reconciliation_without_resource") is True:
                return False
        return True

    def _dispatch(self):
        self.ensure_one()
        # The reservation was committed before entering this transaction. Hold the
        # row lock throughout network IO and result persistence so reconciliation
        # cannot declare a request unapplied while a worker is still sending it.
        # Recheck after locking: reconciliation may have won the post-commit race.
        self._lock()
        if self.state != "dispatching":
            raise UserError(_("Command was not reserved for dispatch."))
        digest = hashlib.sha256(json.dumps(self.payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if digest != self.payload_digest or not self.checker_id or self.checker_id == self.maker_id:
            self.write({"state": "failed", "completed_at": fields.Datetime.now(), "status_message": _("Command integrity or approval check failed.")})
            return
        request_sent = False
        try:
            maker_group = "mfierp.group_manager" if self._requires_administrator() else "mfierp.group_operator"
            checker_group = "mfierp.group_manager" if self._requires_administrator() else "mfierp.group_checker"
            for user, group in [(self.maker_id, maker_group), (self.checker_id, checker_group)]:
                if not user.active or self.company_id not in user.company_ids or not user.has_group(group):
                    raise AccessError(_("Command participants no longer have the required role or company access."))
            if self.operation == "workspace":
                method, path, params, body = self._workspace_request()
                if method == "GET":
                    raise ValueError("A command cannot dispatch a read workflow.")
            else:
                method = "POST"
                path, params = build_request(self.operation, self.remote_target_id, self.payload)
                body = self.payload
            backend = self.backend_id.sudo()
            if not backend.active or backend.environment == "production" or not backend.mutation_enabled:
                raise UserError(_("Financial dispatch is disabled for this connection."))
            client = backend._client()
            backend._verify_runtime(client)
            if self.datatable_id:
                self.datatable_id._verify_metadata(client)
            files = None
            if self.operation == "workspace":
                body, files = self._workspace_body(body)
            request_sent = True
            result = client.request(method, path, params=params,
                payload=body, idempotency_key=self.idempotency_key,
                **({"allow_empty": True, "api_version": self._workspace_specification().get("api_version", "v1"),
                    **({"files": files} if files is not None else {})} if self.operation == "workspace" else {}))
            if self.operation == "workspace":
                spec = self._workspace_specification()
                if spec.get("response_mode") == "collection_preview":
                    preview = project_preview(result)
                    self.write({"preview_data": preview, "preview_digest": hashlib.sha256(json.dumps(preview, sort_keys=True).encode()).hexdigest(),
                        "state": "done", "completed_at": fields.Datetime.now(), "status_message": _("Fineract collection preview received. No collection posting was requested.")})
                    return
                if spec.get("require_reconciliation"):
                    resource_id, command_id = workspace.command_references(result)
                    subresource_id = workspace.subresource_reference(result) if spec.get("capture_subresource") else None
                    messages = {
                        "dividend": _("Dividend response received. Reconcile the payout plan and affected accounts. Approval does not establish completed payment."),
                        "collection": _("Collection response received. Reconcile every affected account and transaction before confirming the posting."),
                    }
                    message = messages.get(spec.get("reconciliation_scope"),
                        _("Remote response received. Verify every affected resource and account before confirming the outcome."))
                    self.write({"state": "remote_pending", "completed_at": fields.Datetime.now(),
                        "result_resource_id": resource_id, "result_command_id": command_id,
                        "result_subresource_id": subresource_id, "status_message": message})
                    return
            resource_id, command_id = workspace.command_references(result)
            if self.operation == "workspace" and (not isinstance(result, dict) or not (result.get("resourceId") or result.get("commandId"))):
                self.write({"state": "remote_pending", "completed_at": fields.Datetime.now(),
                    "status_message": _("Fineract accepted the request. Re-read and reconcile the affected resource or job before confirming its outcome.")})
                return
            if not isinstance(result, dict) or not (result.get("resourceId") or result.get("commandId")):
                raise FineractError("Unrecognized command response; reconcile with Fineract.", uncertain=True)
            # A commandId without resourceId may mean Fineract's own maker checker queue.
            state = "done" if result.get("resourceId") else "remote_pending"
            self.write({"state": state, "result_resource_id": resource_id,
                "result_command_id": command_id, "completed_at": fields.Datetime.now(),
                "status_message": _("Remote response recorded. Refresh the portfolio to verify current state.")})
        except FineractError as exc:
            self.write({"state": "uncertain" if exc.uncertain else "failed", "status_message": str(exc),
                "completed_at": False if exc.uncertain else fields.Datetime.now()})
        except (AccessError, UserError, ValueError):
            self.write({"state": "uncertain" if request_sent else "failed", "completed_at": False if request_sent else fields.Datetime.now(),
                "status_message": _("Response processing failed after dispatch; reconcile before resubmitting.") if request_sent else _("Connection configuration or command validation failed before dispatch.")})

    @api.model
    def _cron_dispatch(self):
        """Persist the sending barrier BEFORE network IO using the cron transaction API.

        A worker crash after reservation leaves dispatching, which is NEVER automatically
        replayed. Odoo's _commit_progress is intentional here, rather than cr.commit().
        """
        for _index in range(20):
            self.flush_model(["state"])
            self.env.cr.execute("SELECT id FROM mfierp_command WHERE state = 'approved' ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1")
            row = self.env.cr.fetchone()
            if not row:
                break
            command = self.sudo().browse(row[0])
            command.write({"state": "dispatching", "dispatched_at": fields.Datetime.now()})
            if not self.env["ir.cron"]._commit_progress(0):
                # Reservation remains deliberate: reconcile rather than risk duplicate money movement.
                return
            command._dispatch()
            if not self.env["ir.cron"]._commit_progress(1):
                return

    def action_reconcile(self):
        self.ensure_one()
        self.check_access("read")
        if not self.env.user.has_group("mfierp.group_manager"):
            raise AccessError(_("An MFIERP administrator must reconcile uncertain results."))
        return {"type": "ir.actions.act_window", "name": _("Record Fineract Reconciliation"),
            "res_model": "mfierp.reconcile", "view_mode": "form", "target": "new",
            "context": {"default_command_id": self.id}}
