# SPDX-License-Identifier: LGPL-3.0-or-later
import base64
import hashlib

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.binary import BinaryValue


def upload_bytes(data):
    if isinstance(data, BinaryValue):
        if not 0 < data.size <= 8 * 1024 * 1024:
            raise UserError(_("Upload a non-empty file of at most 8 MiB."))
        return data.content
    if data and len(data) > ((8 * 1024 * 1024 + 2) // 3) * 4:
        raise UserError(_("Upload a file of at most 8 MiB."))
    try:
        raw = base64.b64decode(data or b"", validate=True)
    except (ValueError, TypeError) as exc:
        raise UserError(_("Upload is not valid encoded file data.")) from exc
    if not raw or len(raw) > 8 * 1024 * 1024:
        raise UserError(_("Upload a non-empty file of at most 8 MiB."))
    return raw


class MfierpUpload(models.Model):
    _name = "mfierp.upload"
    _description = "Protected Pending Fineract Upload"
    _check_company_auto = True

    name = fields.Char(required=True, readonly=True)
    backend_id = fields.Many2one("mfierp.backend", required=True, readonly=True, ondelete="restrict", check_company=True)
    company_id = fields.Many2one(related="backend_id.company_id", store=True, index=True)
    command_id = fields.Many2one("mfierp.command", readonly=True, ondelete="restrict", check_company=True, index=True)
    data = fields.Binary(readonly=True, attachment=True)
    sha256 = fields.Char(required=True, readonly=True)
    purged_at = fields.Datetime(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_("Uploads are captured only through an authorized workflow form."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            raise AccessError(_("Submitted uploads are immutable."))
        return super().write(vals)

    def unlink(self):
        raise AccessError(_("Upload audit references cannot be deleted manually."))

    def _verified_bytes(self, command, marker):
        self.ensure_one()
        if self.command_id != command or self.backend_id != command.backend_id or self.sha256 != marker["sha256"] or self.name != marker["name"]:
            raise UserError(_("Upload does not match the reviewed command."))
        raw = upload_bytes(self.data)
        if hashlib.sha256(raw).hexdigest() != self.sha256:
            raise UserError(_("Upload integrity check failed."))
        return raw

    @api.model
    def _cron_purge(self):
        # Preserve audit metadata. Never purge pending/unknown remote outcomes.
        cutoff = fields.Datetime.subtract(fields.Datetime.now(), days=7)
        records = self.sudo().search([("purged_at", "=", False), ("command_id.state", "in", ["done", "failed", "rejected"]),
            ("command_id.completed_at", "<", cutoff)], limit=100)
        records.write({"data": False, "purged_at": fields.Datetime.now()})
