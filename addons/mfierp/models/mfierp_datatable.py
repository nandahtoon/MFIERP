# SPDX-License-Identifier: LGPL-3.0-or-later
import hashlib
import json
from urllib.parse import quote

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from ..services import datatables, workspace
from ..services.fineract import FineractError


class MfierpDatatable(models.Model):
    _name = "mfierp.datatable"
    _description = "Registered Fineract Data Table"
    _order = "backend_id, application_table, name"
    _check_company_auto = True

    name = fields.Char(required=True, readonly=True)
    backend_id = fields.Many2one("mfierp.backend", required=True, readonly=True, ondelete="restrict", check_company=True)
    company_id = fields.Many2one(related="backend_id.company_id", store=True, index=True)
    application_table = fields.Char(readonly=True)
    executable = fields.Boolean(readonly=True)
    multi_row = fields.Boolean(readonly=True)
    blocked_reason = fields.Char(readonly=True)
    metadata_json = fields.Json(readonly=True, groups="mfierp.group_manager")
    metadata_digest = fields.Char(readonly=True)
    refreshed_at = fields.Datetime(readonly=True)

    _table_unique = models.Constraint("UNIQUE(backend_id, name)", "Registered table names must be unique per connection.")

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_("Data table contracts must be discovered from Fineract."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            raise AccessError(_("Discovered table contracts are read-only."))
        return super().write(vals)

    def unlink(self):
        raise AccessError(_("Registered table contracts are retained for command audit."))

    def _specification(self, action):
        self.ensure_one()
        if not self.executable:
            raise UserError(self.blocked_reason or _("Refresh this table's contract before use."))
        try:
            return datatables.specification(self.sudo().metadata_json, action)
        except ValueError as exc:
            raise UserError(str(exc)) from exc

    def _assert_role(self, action):
        self.ensure_one()
        self.check_access("read")
        spec = self._specification(action)
        group = "mfierp.group_manager" if spec["admin_only"] else "mfierp.group_reader" if action == "read" else "mfierp.group_operator"
        if not self.env.user.has_group(group):
            raise AccessError(_("Your MFIERP role does not allow this data table action."))
        self.backend_id.check_access("read")
        if not self.backend_id.active or self.company_id not in self.env.companies:
            raise AccessError(_("Choose an active connection in an allowed company."))
        return spec

    def _contract_digest(self, action):
        self._specification(action)
        context = ["datatable-entry-v1", workspace.catalog_fingerprint(), self.backend_id.id, self.company_id.id,
            self.metadata_digest, action]
        return hashlib.sha256(json.dumps(context, separators=(",", ":")).encode()).hexdigest()

    def _build_request(self, action, envelope):
        return workspace.build_spec_request(self._specification(action), envelope, self._contract_digest(action))

    def _verify_metadata(self, client):
        self.ensure_one()
        result = client.request("GET", "datatables/" + quote(datatables.identifier(self.name), safe=""))
        if datatables.fingerprint(result) != self.metadata_digest:
            raise UserError(_("Fineract's table metadata changed. Refresh the table contract and submit a new reviewed request."))

    def _open(self, action):
        self._assert_role(action)
        context = {"default_datatable_id": self.id, "default_datatable_action": action,
            "default_backend_id": self.backend_id.id, "default_company_id": self.company_id.id}
        if self.env.context.get("default_target_id"):
            context["default_target_id"] = self.env.context["default_target_id"]
        return {"type": "ir.actions.act_window", "name": self.name, "res_model": "mfierp.request",
            "view_mode": "form", "target": "current", "context": context}

    def action_read_entries(self):
        return self._open("read")

    def action_create_entry(self):
        return self._open("create")

    def action_update_entry(self):
        return self._open("update")

    def action_delete_entry(self):
        return self._open("delete")


class MfierpBackend(models.Model):
    _inherit = "mfierp.backend"

    def action_refresh_datatables(self):
        self.ensure_one()
        self.check_access("read")
        if not self.env.user.has_group("mfierp.group_manager") or self.company_id not in self.env.companies or not self.active:
            raise AccessError(_("An administrator must select an active connection in an allowed company."))
        try:
            registrations = self._client().request("GET", "datatables")
        except FineractError as exc:
            raise UserError(str(exc)) from exc
        if not isinstance(registrations, list) or len(registrations) > 500:
            raise UserError(_("Expected a bounded list of registered tables."))
        names = set()
        tables = self.env["mfierp.datatable"].sudo()
        for metadata in registrations:
            try:
                name = datatables.identifier(metadata.get("registeredTableName") if isinstance(metadata, dict) else None)
            except ValueError as exc:
                raise UserError(str(exc)) from exc
            if name in names:
                raise UserError(_("Fineract returned duplicate table registrations."))
            names.add(name)
            vals = {"name": name, "backend_id": self.id, "metadata_json": False, "metadata_digest": False,
                "executable": False, "multi_row": False, "application_table": str(metadata.get("applicationTableName", ""))[:100],
                "refreshed_at": fields.Datetime.now(), "blocked_reason": False}
            try:
                compiled = datatables.compile_table(metadata)
                vals.update(metadata_json=compiled["metadata"], metadata_digest=datatables.fingerprint(metadata),
                    executable=True, multi_row=compiled["multi_row"])
            except ValueError as exc:
                vals["blocked_reason"] = str(exc)
            record = tables.search([("backend_id", "=", self.id), ("name", "=", name)], limit=1)
            if record:
                record.write(vals)
            else:
                tables.create(vals)
        tables.search([("backend_id", "=", self.id), ("name", "not in", list(names))]).write({
            "executable": False, "blocked_reason": _("This table is no longer registered in Fineract."), "refreshed_at": fields.Datetime.now()})
        return {"type": "ir.actions.act_window", "name": _("Registered Data Tables"), "res_model": "mfierp.datatable",
            "view_mode": "list,form", "domain": [("backend_id", "=", self.id)]}
