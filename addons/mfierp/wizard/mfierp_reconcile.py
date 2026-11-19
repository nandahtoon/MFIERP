# SPDX-License-Identifier: LGPL-3.0-or-later
from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError


class MfierpReconcile(models.TransientModel):
    _name = "mfierp.reconcile"
    _description = "Record Remote Command Reconciliation"

    command_id = fields.Many2one("mfierp.command", required=True, readonly=True)
    outcome = fields.Selection([("done", "Confirmed Applied"), ("failed", "Confirmed Not Applied")], required=True)
    resource_id = fields.Integer(string="Verified Fineract Resource ID")
    note = fields.Text(required=True, help="Record independently verified transaction IDs, remote audit reference and investigation outcome.")

    def action_record(self):
        self.ensure_one()
        self.check_access("read")
        if not self.env.user.has_group("mfierp.group_manager"):
            raise AccessError(_("An MFIERP administrator role is required."))
        command = self.command_id
        command._lock()
        if command.state not in {"dispatching", "uncertain", "remote_pending"}:
            raise UserError(_("Only unconfirmed commands can be reconciled."))
        if len((self.note or "").strip()) < 20:
            raise UserError(_("Provide at least 20 characters of independent verification evidence."))
        if self.outcome == "done" and self.resource_id <= 0:
            raise UserError(_("A verified remote resource ID is required for an applied command."))
        command.sudo().write({"state": self.outcome, "result_resource_id": self.resource_id,
            "resolution_note": self.note, "resolved_by_id": self.env.uid, "completed_at": fields.Datetime.now(),
            "status_message": _("Reconciled from independently verified Fineract evidence; no request resent.")})
        return {"type": "ir.actions.act_window_close"}
