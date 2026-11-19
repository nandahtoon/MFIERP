# SPDX-License-Identifier: LGPL-3.0-or-later
import hashlib
import json
import uuid

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from ..services.fineract import FineractError
from ..services.operations import OPERATIONS, build_request


class MfierpCommand(models.Model):
    _name = "mfierp.command"
    _description = "Fineract Maker Checker Command"
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(readonly=True, required=True)
    backend_id = fields.Many2one("mfierp.backend", string="Connection", required=True, readonly=True, ondelete="restrict", check_company=True)
    company_id = fields.Many2one(related="backend_id.company_id", store=True, index=True)
    operation = fields.Selection([(key, item[0]) for key, item in OPERATIONS.items()], readonly=True, required=True)
    target_id = fields.Many2one("mfierp.record", readonly=True, ondelete="restrict", check_company=True)
    remote_target_id = fields.Integer(readonly=True)
    payload = fields.Json(readonly=True)
    payload_preview = fields.Text(string="Request Details", compute="_compute_payload_preview")
    payload_digest = fields.Char(readonly=True)
    idempotency_key = fields.Char(readonly=True, required=True, index=True)
    state = fields.Selection([
        ("pending", "Awaiting Approval"), ("approved", "Approved"), ("dispatching", "Dispatching"),
        ("done", "Confirmed"), ("remote_pending", "Fineract Approval Pending"),
        ("rejected", "Rejected"), ("failed", "Rejected by Fineract"), ("uncertain", "Reconciliation Required"),
    ], default="pending", readonly=True, required=True, index=True)
    maker_id = fields.Many2one("res.users", readonly=True, required=True)
    checker_id = fields.Many2one("res.users", readonly=True)
    approved_at = fields.Datetime(readonly=True)
    dispatched_at = fields.Datetime(readonly=True)
    completed_at = fields.Datetime(readonly=True)
    result_resource_id = fields.Integer(readonly=True)
    result_command_id = fields.Integer(readonly=True)
    status_message = fields.Char(readonly=True)
    resolution_note = fields.Text(readonly=True)
    resolved_by_id = fields.Many2one("res.users", readonly=True)

    _key_unique = models.Constraint("UNIQUE(idempotency_key)", "Command idempotency keys must be unique.")

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

    def action_approve(self):
        self._lock()
        if not self.env.user.has_group("mfierp.group_checker"):
            raise AccessError(_("An MFIERP checker role is required."))
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
        if self.state != "pending":
            raise UserError(_("Only pending commands can be rejected."))
        self.sudo().write({"state": "rejected", "checker_id": self.env.uid, "completed_at": fields.Datetime.now()})
        return True

    def _dispatch(self):
        self.ensure_one()
        if self.state != "dispatching":
            raise UserError(_("Command was not reserved for dispatch."))
        digest = hashlib.sha256(json.dumps(self.payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if digest != self.payload_digest or not self.checker_id or self.checker_id == self.maker_id:
            self.write({"state": "failed", "status_message": _("Command integrity or approval check failed.")})
            return
        try:
            path, params = build_request(self.operation, self.remote_target_id, self.payload)
            backend = self.backend_id.sudo()
            if backend.environment == "production" or not backend.mutation_enabled:
                raise UserError(_("Financial dispatch is disabled for this connection."))
            client = backend._client()
            backend._verify_runtime(client)
            result = client.request("POST", path, params=params,
                payload=self.payload, idempotency_key=self.idempotency_key)
            if not isinstance(result, dict) or not (result.get("resourceId") or result.get("commandId")):
                raise FineractError("Unrecognized command response; reconcile with Fineract.", uncertain=True)
            # A commandId without resourceId may mean Fineract's own maker checker queue.
            state = "done" if result.get("resourceId") else "remote_pending"
            self.write({"state": state, "result_resource_id": result.get("resourceId"),
                "result_command_id": result.get("commandId"), "completed_at": fields.Datetime.now(),
                "status_message": _("Remote response recorded. Refresh the portfolio to verify current state.")})
        except FineractError as exc:
            self.write({"state": "uncertain" if exc.uncertain else "failed", "status_message": str(exc)})
        except (UserError, ValueError):
            self.write({"state": "failed", "status_message": _("Connection configuration or command validation failed before dispatch.")})

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
