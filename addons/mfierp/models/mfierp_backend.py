# SPDX-License-Identifier: LGPL-3.0-or-later
import os
import re

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..services.fineract import FineractClient, FineractError, validate_url
from ..services.operations import RESOURCES


class MfierpBackend(models.Model):
    _name = "mfierp.backend"
    _description = "Fineract Connection"
    _check_company_auto = True

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    base_url = fields.Char(required=True, help="HTTPS base URL ending in /fineract-provider/api/v1")
    tenant = fields.Char(required=True, default="default")
    environment = fields.Selection([("development", "Development / Contract"), ("staging", "Canonical Staging"),
        ("production", "Production — Writes Blocked")], required=True, default="development")
    mutation_enabled = fields.Boolean(default=False, groups="mfierp.group_manager",
        help="Enable only for an approved synthetic development/staging acceptance lane. Production dispatch is blocked.")
    expected_version = fields.Char(groups="mfierp.group_manager", help="Exact version from Fineract actuator/info.")
    expected_commit = fields.Char(groups="mfierp.group_manager", help="Exact 40-character Fineract Git commit from actuator/info.")
    observed_version = fields.Char(readonly=True)
    observed_commit = fields.Char(readonly=True)
    verified_at = fields.Datetime(readonly=True)
    credential_prefix = fields.Char(required=True, default="MFIERP_DEFAULT",
        groups="mfierp.group_manager", help="Environment prefix; reads <PREFIX>_USERNAME and <PREFIX>_PASSWORD")
    timeout = fields.Integer(default=30, required=True)
    sync_enabled = fields.Boolean(default=False, help="Enable scheduled read synchronization for this connection.")
    last_sync = fields.Datetime(readonly=True)
    sync_status = fields.Char(readonly=True)
    record_ids = fields.One2many("mfierp.record", "backend_id")

    @api.constrains("base_url", "tenant", "credential_prefix", "timeout")
    def _check_configuration(self):
        for backend in self:
            try:
                validate_url(backend.base_url)
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", backend.tenant or ""):
                raise ValidationError(_("Use a valid Fineract tenant identifier."))
            if not re.fullmatch(r"MFIERP_[A-Z0-9_]{1,80}", backend.credential_prefix or ""):
                raise ValidationError(_("Credential prefix must start with MFIERP_ and use uppercase letters, digits or underscores."))
            if not 5 <= backend.timeout <= 120:
                raise ValidationError(_("Timeout must be between 5 and 120 seconds."))

    def write(self, vals):
        if {"company_id", "base_url", "tenant", "environment", "expected_version", "expected_commit"} & vals.keys():
            for backend in self:
                if (self.env["mfierp.record"].sudo().search_count([("backend_id", "=", backend.id)])
                        or self.env["mfierp.command"].sudo().search_count([("backend_id", "=", backend.id)])
                        or self.env["mfierp.datatable"].sudo().search_count([("backend_id", "=", backend.id)])):
                    raise UserError(_("Create a new connection to change company, URL, tenant, environment or runtime pin after use."))
        return super().write(vals)

    def _client(self):
        self.ensure_one()
        if not self.active:
            raise UserError(_("This Fineract connection is archived."))
        prefix = self.sudo().credential_prefix
        try:
            return FineractClient(self.base_url, self.tenant,
                os.environ.get(f"{prefix}_USERNAME"), os.environ.get(f"{prefix}_PASSWORD"), self.timeout)
        except ValueError as exc:
            raise UserError(_("Check the connection URL, tenant and deployment credentials.")) from exc

    def action_test_connection(self):
        self.ensure_one()
        self.check_access("read")
        if not self.env.user.has_group("mfierp.group_manager"):
            raise AccessError(_("Only MFIERP administrators can test connections."))
        try:
            client = self._client()
            self._verify_runtime(client, require_pin=False)
            client.request("GET", "offices")
        except FineractError as exc:
            raise UserError(str(exc)) from exc
        return {"type": "ir.actions.client", "tag": "display_notification", "params": {
            "title": _("Fineract connection verified"), "message": _("Office API is reachable."), "type": "success"}}

    def _verify_runtime(self, client, require_pin=True):
        self.ensure_one()
        info = client.info()
        if not isinstance(info, dict):
            raise UserError(_("Fineract runtime provenance is unavailable."))
        git = info.get("git") or {}
        version = (git.get("build") or {}).get("version") or (info.get("build") or {}).get("version")
        commit = ((git.get("commit") or {}).get("id") or {}).get("full")
        if not isinstance(version, str) or not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise UserError(_("Fineract must expose a version and full commit in actuator/info."))
        self.sudo().write({"observed_version": version, "observed_commit": commit, "verified_at": fields.Datetime.now()})
        pin = self.sudo()
        if require_pin and (not pin.expected_version or not pin.expected_commit):
            raise UserError(_("An administrator must pin the verified Fineract version and commit before dispatch."))
        if pin.expected_version and pin.expected_version != version:
            raise UserError(_("The Fineract version differs from the reviewed connection pin."))
        if pin.expected_commit and pin.expected_commit != commit:
            raise UserError(_("The Fineract commit differs from the reviewed connection pin."))

    def action_sync(self):
        self.ensure_one()
        self.check_access("read")
        if not self.env.user.has_group("mfierp.group_manager"):
            raise AccessError(_("Only MFIERP administrators can synchronize connections."))
        try:
            self._sync()
        except FineractError as exc:
            raise UserError(str(exc)) from exc
        return True

    def _sync(self):
        self.ensure_one()
        client = self._client()
        count = 0
        for kind, (path, _label) in RESOURCES.items():
            for page in client.pages(path):
                for row in page:
                    self.env["mfierp.record"]._upsert(self, kind, row)
                    count += 1
        self.sudo().write({"last_sync": fields.Datetime.now(), "sync_status": _("Synchronized %s records", count)})

    @api.model
    def _cron_sync(self):
        for backend in self.sudo().search([("sync_enabled", "=", True)]):
            try:
                with self.env.cr.savepoint():
                    backend._sync()
            except (FineractError, UserError):
                backend.write({"sync_status": _("Synchronization failed. Check remote permissions and connectivity; previous snapshots retained.")})
