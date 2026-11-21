# SPDX-License-Identifier: LGPL-3.0-or-later
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from ..services import workspace


class MfierpCapability(models.Model):
    _name = "mfierp.capability"
    _description = "Source-backed Fineract Workflow Contract"
    _order = "category, name, method"

    key = fields.Char(required=True, readonly=True, index=True)
    name = fields.Char(required=True, readonly=True)
    category = fields.Char(readonly=True, index=True)
    method = fields.Char(readonly=True, index=True)
    resource = fields.Char(readonly=True, index=True)
    context_resource = fields.Char(readonly=True, index=True)
    description = fields.Text(readonly=True)
    executable = fields.Boolean(readonly=True, index=True)
    blocked_reason = fields.Char(readonly=True)
    admin_only = fields.Boolean(readonly=True)
    source_version = fields.Char(readonly=True)

    _key_unique = models.Constraint("UNIQUE(key)", "Workflow contracts must have unique keys.")

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_("Workflow contracts are maintained from reviewed source files."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            raise AccessError(_("Workflow contracts are read-only."))
        return super().write(vals)

    def unlink(self):
        raise AccessError(_("Workflow contracts cannot be removed through the interface."))

    @api.model
    def _sync_catalog(self):
        version = workspace.catalog()["api_version"]
        stale = self.sudo().search([("key", "not in", list(workspace.capabilities()))])
        stale.write({"executable": False, "blocked_reason": "This contract was removed from the reviewed catalog."})
        for key, spec in workspace.capabilities().items():
            vals = {"key": key, "name": spec["name"][:250], "category": spec["category"], "method": spec["method"],
                "resource": spec["path"].removeprefix("/" + spec.get("api_version", "v1") + "/").split("/")[0], "description": spec["description"],
                "context_resource": spec.get("context_resource"),
                "executable": not bool(spec["blocked"]), "blocked_reason": spec["blocked"],
                "admin_only": spec["admin_only"], "source_version": version}
            record = self.sudo().search([("key", "=", key)], limit=1)
            if record:
                record.write(vals)
            else:
                self.sudo().create(vals)

    def _assert_role(self):
        self.ensure_one()
        self.check_access("read")
        spec = workspace.specification(self.key)
        if spec["blocked"]:
            raise UserError(spec["blocked"])
        group = "mfierp.group_manager" if spec["admin_only"] else "mfierp.group_reader" if spec["method"] == "GET" else "mfierp.group_operator"
        if not self.env.user.has_group(group):
            raise AccessError(_("Your MFIERP role does not allow this workflow."))
        return spec

    def action_open(self):
        self._assert_role()
        context = {"default_capability_id": self.id}
        for key in ("backend_id", "company_id", "target_id"):
            value = self.env.context.get("default_" + key)
            if value:
                context["default_" + key] = value
        return {"type": "ir.actions.act_window", "name": self.name, "res_model": "mfierp.request",
            "view_mode": "form", "target": "current", "context": context}
