# SPDX-License-Identifier: LGPL-3.0-or-later
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from ..services.operations import OPERATIONS


class MfierpOperation(models.TransientModel):
    _name = "mfierp.operation"
    _description = "Submit a Fineract Operation"
    _check_company_auto = True

    backend_id = fields.Many2one("mfierp.backend", string="Fineract Connection", required=True, check_company=True, domain="[('active', '=', True)]")
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    operation = fields.Selection([(key, item[0]) for key, item in OPERATIONS.items()], required=True, default="create_client")
    target_id = fields.Many2one("mfierp.record", check_company=True,
        domain="[('backend_id', '=', backend_id), ('kind', '=', resource_kind)]")
    resource_kind = fields.Char(compute="_compute_operation")
    is_create = fields.Boolean(compute="_compute_operation")
    needs_amount = fields.Boolean(compute="_compute_operation")
    office_id = fields.Many2one("mfierp.record", check_company=True, domain="[('backend_id', '=', backend_id), ('kind', '=', 'office')]")
    client_id = fields.Many2one("mfierp.record", check_company=True, domain="[('backend_id', '=', backend_id), ('kind', '=', 'client')]")
    product_id = fields.Many2one("mfierp.record", check_company=True,
        domain="[('backend_id', '=', backend_id), ('kind', '=', resource_kind + '_product')]")
    firstname = fields.Char(string="First Name")
    lastname = fields.Char(string="Last Name")
    name = fields.Char(string="Group / Center Name")
    mobile_no = fields.Char(string="Mobile Number")
    external_id = fields.Char(string="External Reference", help="If blank, the submitted create command receives a stable MFIERP UUID reference for remote reconciliation.")
    operation_date = fields.Date(required=True, default=fields.Date.context_today)
    expected_disbursement_date = fields.Date(default=fields.Date.context_today)
    amount = fields.Float(digits=(20, 6))
    payment_type_id = fields.Integer(help="Optional Fineract payment type ID. Obtain from your tenant's payment types.")
    note = fields.Text()
    loan_term = fields.Integer(default=12)
    loan_term_unit = fields.Selection([("0", "Days"), ("1", "Weeks"), ("2", "Months"), ("3", "Years")], default="2")
    repayments = fields.Integer(default=12)
    repayment_every = fields.Integer(default=1)
    repayment_unit = fields.Selection([("0", "Days"), ("1", "Weeks"), ("2", "Months"), ("3", "Years")], default="2")
    interest_rate = fields.Float(digits=(12, 6), help="Rate per period in the selected product's interest period unit.")
    amortization = fields.Selection([("0", "Equal Principal"), ("1", "Equal Installments")], default="1")
    interest_type = fields.Selection([("0", "Declining Balance"), ("1", "Flat")], default="0")
    interest_period = fields.Selection([("0", "Daily"), ("1", "Same as Repayment Period")], default="1")
    strategy_code = fields.Char(help="Fineract transaction processing strategy code from the selected loan product.")

    @api.depends("operation")
    def _compute_operation(self):
        for wizard in self:
            wizard.resource_kind = OPERATIONS.get(wizard.operation, (None, ""))[1]
            wizard.is_create = bool(wizard.operation and wizard.operation.startswith("create_"))
            wizard.needs_amount = wizard.operation in {"create_loan", "repay_loan", "deposit_savings", "withdraw_savings"}

    @api.onchange("target_id")
    def _onchange_target_id(self):
        if self.target_id:
            defaults = {"client": "activate_client", "group": "activate_group", "center": "activate_center",
                "loan": "repay_loan", "savings": "deposit_savings"}
            self.operation = defaults.get(self.target_id.kind, "create_client")

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id and self.resource_kind == "loan":
            self._remote_id(self.product_id, "loan_product")
            # Product data is fetched server-side, never exposed to users lacking raw-data access.
            data = self.product_id.sudo().raw_data or {}
            self.interest_rate = data.get("interestRatePerPeriod", 0)
            self.repayments = data.get("numberOfRepayments", 12)
            self.repayment_every = data.get("repaymentEvery", 1)
            self.strategy_code = data.get("transactionProcessingStrategyCode")
            for remote, local in [("amortizationType", "amortization"), ("interestType", "interest_type"),
                    ("interestCalculationPeriodType", "interest_period"), ("repaymentFrequencyType", "repayment_unit")]:
                value = data.get(remote)
                if isinstance(value, dict):
                    setattr(self, local, str(value["id"]))

    def _remote_id(self, record, kind):
        if not record:
            raise UserError(_("Choose a %s record.", kind))
        record.check_access("read")
        if record.backend_id != self.backend_id or record.kind != kind:
            raise UserError(_("Selected records must belong to the operation's connection and resource type."))
        return record.remote_id

    def _payload(self):
        self.ensure_one()
        op = self.operation
        dt = fields.Date.to_string(self.operation_date)
        payload = {"dateFormat": "yyyy-MM-dd", "locale": "en"}
        if op in {"create_client", "create_group", "create_center"}:
            payload.update(officeId=self._remote_id(self.office_id, "office"), active=False)
            if op != "create_center":
                payload["submittedOnDate"] = dt
            if op == "create_client":
                if not (self.firstname or "").strip() or not (self.lastname or "").strip():
                    raise UserError(_("First name and last name are required."))
                payload.update(firstname=self.firstname.strip(), lastname=self.lastname.strip())
                if self.mobile_no:
                    payload["mobileNo"] = self.mobile_no
            else:
                if not (self.name or "").strip():
                    raise UserError(_("Group or center name is required."))
                payload["name"] = self.name.strip()
        elif op in {"create_loan", "create_savings"}:
            payload.update(clientId=self._remote_id(self.client_id, "client"),
                productId=self._remote_id(self.product_id, self.resource_kind + "_product"), submittedOnDate=dt)
            if op == "create_loan":
                if min(self.loan_term, self.repayments, self.repayment_every) <= 0 or self.interest_rate < 0:
                    raise UserError(_("Loan term and repayment counts must be positive, and interest cannot be negative."))
                if not self.strategy_code or not self.expected_disbursement_date:
                    raise UserError(_("Choose an expected disbursement date and a transaction processing strategy."))
                payload.update(principal=self.amount, loanType="individual", loanTermFrequency=self.loan_term,
                    loanTermFrequencyType=int(self.loan_term_unit), numberOfRepayments=self.repayments,
                    repaymentEvery=self.repayment_every, repaymentFrequencyType=int(self.repayment_unit),
                    interestRatePerPeriod=self.interest_rate, amortizationType=int(self.amortization),
                    interestType=int(self.interest_type), interestCalculationPeriodType=int(self.interest_period),
                    transactionProcessingStrategyCode=self.strategy_code,
                    expectedDisbursementDate=fields.Date.to_string(self.expected_disbursement_date))
        else:
            date_keys = {"activate_client": "activationDate", "activate_group": "activationDate", "activate_center": "activationDate",
                "approve_loan": "approvedOnDate", "disburse_loan": "actualDisbursementDate", "reject_loan": "rejectedOnDate",
                "withdraw_loan": "withdrawnOnDate", "approve_savings": "approvedOnDate", "activate_savings": "activatedOnDate",
                "reject_savings": "rejectedOnDate", "close_savings": "closedOnDate"}
            payload[date_keys.get(op, "transactionDate")] = dt
            if self.needs_amount:
                payload["transactionAmount"] = self.amount
        optional = OPERATIONS[op][5]
        for key, value in [("externalId", self.external_id), ("note", self.note), ("paymentTypeId", self.payment_type_id)]:
            if key in optional and value:
                payload[key] = value
        return payload

    def action_submit(self):
        self.ensure_one()
        self.check_access("read")
        if not self.env.user.has_group("mfierp.group_operator"):
            raise AccessError(_("An MFIERP operator role is required."))
        if self.is_create and self.target_id:
            raise UserError(_("Clear the target for a create operation."))
        command = self.env["mfierp.command"]._enqueue(self.backend_id, self.operation, self._payload(), self.target_id)
        return {"id": self.env.ref("mfierp.mfierp_command_action").id,
            "type": "ir.actions.act_window", "name": _("Submitted Command"),
            "res_model": "mfierp.command", "res_id": command.id, "view_mode": "form", "target": "current"}
