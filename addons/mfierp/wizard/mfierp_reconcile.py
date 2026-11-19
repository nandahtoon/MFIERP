# SPDX-License-Identifier: LGPL-3.0-or-later
from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError

from ..services.fineract import FineractError


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
            # Only scheduler start/stop have a verified resource-less completion
            # contract. Never treat missing IDs on financial writes as success.
            if command.operation != "workspace" or not command.capability_id:
                raise UserError(_("A verified remote resource ID is required for an applied command."))
            try:
                method, path, params, _body = command._workspace_request()
            except (TypeError, ValueError, UserError) as exc:
                raise UserError(_("The scheduler contract is no longer valid; reconciliation is blocked.")) from exc
            if method != "POST" or path != "scheduler" or params not in (
                    {"command": "start"}, {"command": "stop"}):
                raise UserError(_("A verified remote resource ID is required for an applied command."))
            if command.maker_id == self.env.user:
                raise AccessError(_("A different administrator must independently verify scheduler state."))
            backend = command.backend_id.sudo()
            try:
                client = backend._client()
                backend._verify_runtime(client)
                status = client.request("GET", "scheduler")
            except FineractError as exc:
                raise UserError(_("Cannot verify current Fineract scheduler status.")) from exc
            expected_active = params["command"] == "start"
            if (not isinstance(status, dict) or type(status.get("active")) is not bool
                    or status["active"] != expected_active):
                raise UserError(_("Fineract scheduler status does not confirm the requested state."))
        command.sudo().write({"state": self.outcome, "result_resource_id": self.resource_id,
            "resolution_note": self.note, "resolved_by_id": self.env.uid, "completed_at": fields.Datetime.now(),
            "status_message": _("Reconciled from independently verified Fineract evidence; no request resent.")})
        return {"type": "ir.actions.act_window_close"}
