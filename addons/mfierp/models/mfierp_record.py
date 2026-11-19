# SPDX-License-Identifier: LGPL-3.0-or-later
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from ..services.fineract import FineractError
from ..services.operations import RESOURCES


def remote_date(value):
    if isinstance(value, list) and len(value) == 3:
        return date(*value)
    return value if isinstance(value, str) else False


class MfierpRecord(models.Model):
    _name = "mfierp.record"
    _description = "Fineract Portfolio Record"
    _order = "name, id"
    _check_company_auto = True

    name = fields.Char(required=True, readonly=True)
    backend_id = fields.Many2one("mfierp.backend", string="Connection", required=True, ondelete="restrict", readonly=True, check_company=True, index=True)
    company_id = fields.Many2one(related="backend_id.company_id", store=True, index=True)
    kind = fields.Selection([(key, label) for key, (_, label) in RESOURCES.items()], string="Resource", required=True, readonly=True, index=True)
    remote_id = fields.Integer(string="Fineract ID", required=True, readonly=True, index=True)
    external_id = fields.Char(readonly=True, index=True)
    account_no = fields.Char(string="Account Number", readonly=True, index=True)
    status = fields.Char(readonly=True, index=True)
    office_name = fields.Char(readonly=True, index=True)
    client_name = fields.Char(readonly=True, index=True)
    product_name = fields.Char(readonly=True)
    mobile_no = fields.Char(readonly=True)
    activation_date = fields.Date(readonly=True)
    gl_code = fields.Char(readonly=True)
    entry_type = fields.Char(readonly=True)
    transaction_id = fields.Char(readonly=True)
    journal_date = fields.Date(readonly=True)
    journal_amount = fields.Float(readonly=True, digits=(20, 6), aggregator=False)
    interest_rate = fields.Float(readonly=True, digits=(12, 6), aggregator=False)
    description = fields.Text(readonly=True)
    currency_code = fields.Char(readonly=True)
    principal = fields.Float(readonly=True, digits=(20, 6), aggregator=False)
    outstanding = fields.Float(readonly=True, digits=(20, 6), aggregator=False)
    balance = fields.Float(readonly=True, digits=(20, 6), aggregator=False)
    synced_at = fields.Datetime(string="Snapshot Updated", readonly=True)
    financial_details_at = fields.Datetime(string="Financial Details Updated", readonly=True)
    raw_data = fields.Json(readonly=True, groups="mfierp.group_manager")
    line_ids = fields.One2many("mfierp.line", "record_id", readonly=True)

    _remote_unique = models.Constraint("UNIQUE(backend_id, kind, remote_id)", "This remote record already exists on this connection.")

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_("Portfolio records are maintained through Fineract synchronization."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            raise AccessError(_("Portfolio records are read-only snapshots."))
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            raise AccessError(_("Portfolio records cannot be deleted manually."))
        return super().unlink()

    @api.model
    def _upsert(self, backend, kind, row):
        if not isinstance(row, dict) or not isinstance(row.get("id"), int):
            raise FineractError("Remote record is missing an integer identifier.")
        status = row.get("status") or {}
        currency = row.get("currency") or {}
        summary = row.get("summary") or {}
        projection_keys = {
            "id", "displayName", "name", "accountNo", "externalId", "status", "officeName", "clientName",
            "loanProductName", "savingsProductName", "currency", "principal", "mobileNo", "activationDate",
            "glCode", "entryType", "transactionId", "transactionDate", "amount", "description",
            "interestRatePerPeriod", "nominalAnnualInterestRate", "numberOfRepayments", "repaymentEvery",
            "repaymentFrequencyType", "amortizationType", "interestType", "interestCalculationPeriodType",
            "transactionProcessingStrategyCode", "reportName", "reportType", "reportParameters",
        }
        projection = {key: value for key, value in row.items() if key in projection_keys}
        if summary:
            projection["summary"] = {key: value for key, value in summary.items()
                if key in {"totalOutstanding", "accountBalance", "principalDisbursed"}}
        vals = {
            "backend_id": backend.id, "kind": kind, "remote_id": row["id"],
            "name": row.get("displayName") or row.get("name") or row.get("reportName") or row.get("accountNo") or str(row["id"]),
            "external_id": row.get("externalId") if isinstance(row.get("externalId"), str) else False,
            "account_no": row.get("accountNo"),
            "status": status.get("value", status.get("code")) if isinstance(status, dict) else str(status),
            "office_name": row.get("officeName"), "client_name": row.get("clientName"),
            "product_name": row.get("loanProductName") or row.get("savingsProductName"),
            "mobile_no": row.get("mobileNo"),
            "activation_date": remote_date(row.get("activationDate") or (row.get("timeline") or {}).get("activatedOnDate")),
            "gl_code": row.get("glCode"),
            "entry_type": (row.get("entryType") or {}).get("value") if isinstance(row.get("entryType"), dict) else row.get("entryType"),
            "transaction_id": row.get("transactionId"),
            "journal_date": remote_date(row.get("transactionDate")),
            "journal_amount": row.get("amount", 0),
            "interest_rate": row.get("interestRatePerPeriod", row.get("nominalAnnualInterestRate", 0)),
            "description": row.get("description"),
            "currency_code": currency.get("code"),
            "synced_at": fields.Datetime.now(), "raw_data": projection,
        }
        if "principal" in row:
            vals["principal"] = row["principal"]
        if summary:
            vals.update(principal=row.get("principal", summary.get("principalDisbursed", 0)),
                outstanding=summary.get("totalOutstanding", 0), balance=summary.get("accountBalance", 0),
                financial_details_at=fields.Datetime.now())
        record = self.sudo().search([("backend_id", "=", backend.id), ("kind", "=", kind), ("remote_id", "=", row["id"])], limit=1)
        if record:
            record.write(vals)
        else:
            record = self.sudo().create(vals)
        return record

    def action_refresh(self):
        self.ensure_one()
        self.check_access("read")
        path = f"{RESOURCES[self.kind][0]}/{self.remote_id}"
        params = {"associations": "all"} if self.kind in {"loan", "savings", "client"} else None
        try:
            data = self.backend_id._client().request("GET", path, params=params)
            self._upsert(self.backend_id, self.kind, data)
            if self.kind in {"loan", "savings"}:
                self._replace_lines(data)
        except FineractError as exc:
            raise UserError(str(exc)) from exc
        return True

    def _replace_lines(self, data):
        self.ensure_one()
        self.line_ids.sudo().unlink()
        vals_list = []
        for item in data.get("repaymentSchedule", {}).get("periods", []):
            vals_list.append({"record_id": self.id, "kind": "schedule", "name": str(item.get("period", 0)),
                "date": remote_date(item.get("dueDate")), "amount": item.get("totalDueForPeriod", 0),
                "outstanding": item.get("totalOutstandingForPeriod", 0), "completed": bool(item.get("complete"))})
        for item in data.get("transactions", []):
            typ = item.get("type") or {}
            vals_list.append({"record_id": self.id, "kind": "transaction", "remote_id": item["id"],
                "name": typ.get("value", str(item["id"])), "date": remote_date(item.get("date")),
                "amount": item.get("amount", 0), "completed": not item.get("reversed", item.get("reversedOnDate", False))})
        for item in data.get("charges", []):
            vals_list.append({"record_id": self.id, "kind": "charge", "remote_id": item["id"],
                "name": item.get("name", str(item["id"])), "date": remote_date(item.get("dueDate")),
                "amount": item.get("amount", 0), "outstanding": item.get("amountOutstanding", 0),
                "completed": bool(item.get("paid") or item.get("waived"))})
        if vals_list:
            self.env["mfierp.line"].sudo().create(vals_list)

    def action_operation(self):
        self.ensure_one()
        self.check_access("read")
        if not self.env.user.has_group("mfierp.group_operator"):
            raise AccessError(_("An MFIERP operator role is required."))
        return {"type": "ir.actions.act_window", "name": _("Fineract Operation"),
            "res_model": "mfierp.operation", "view_mode": "form", "target": "new",
            "context": {"default_backend_id": self.backend_id.id, "default_target_id": self.id,
                "default_company_id": self.company_id.id}}

    def action_report(self):
        self.ensure_one()
        self.check_access("read")
        if self.kind != "report":
            raise UserError(_("Choose a report catalog record."))
        return {"type": "ir.actions.act_window", "name": _("Run Fineract Report"),
            "res_model": "mfierp.report", "view_mode": "form", "target": "current",
            "context": {"default_backend_id": self.backend_id.id, "default_report_id": self.id,
                "default_company_id": self.company_id.id}}

    def action_workspace(self):
        self.ensure_one()
        self.check_access("read")
        return {"type": "ir.actions.act_window", "name": _("Related Fineract Workflows"),
            "res_model": "mfierp.capability", "view_mode": "list,form",
            "domain": ["|", ("resource", "=", RESOURCES[self.kind][0]), ("context_resource", "=", RESOURCES[self.kind][0])],
            "context": {"default_backend_id": self.backend_id.id, "default_target_id": self.id,
                "default_company_id": self.company_id.id}}


class MfierpLine(models.Model):
    _name = "mfierp.line"
    _description = "Fineract Schedule, Transaction or Charge"
    _order = "date, id"

    record_id = fields.Many2one("mfierp.record", required=True, ondelete="cascade", readonly=True)
    company_id = fields.Many2one(related="record_id.company_id", store=True, index=True)
    kind = fields.Selection([("schedule", "Repayment Schedule"), ("transaction", "Transaction"), ("charge", "Charge")], required=True, readonly=True)
    remote_id = fields.Integer(readonly=True)
    name = fields.Char(readonly=True)
    date = fields.Date(readonly=True)
    amount = fields.Float(readonly=True, digits=(20, 6), aggregator=False)
    outstanding = fields.Float(readonly=True, digits=(20, 6), aggregator=False)
    currency_code = fields.Char(related="record_id.currency_code")
    completed = fields.Boolean(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_("Only synchronization can create detail records."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            raise AccessError(_("Detail records are read-only."))
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            raise AccessError(_("Detail records are read-only."))
        return super().unlink()
