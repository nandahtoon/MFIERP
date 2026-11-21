# SPDX-License-Identifier: LGPL-3.0-or-later
"""Explicit endpoint registry shared by the typed wizard and dispatch validation."""

from datetime import date
from decimal import Decimal, InvalidOperation


RESOURCES = {
    "office": ("offices", "Offices"),
    "staff": ("staff", "Staff"),
    "client": ("clients", "Clients"),
    "group": ("groups", "Groups"),
    "center": ("centers", "Centers"),
    "loan_product": ("loanproducts", "Loan Products"),
    "savings_product": ("savingsproducts", "Savings Products"),
    "loan": ("loans", "Loans"),
    "savings": ("savingsaccounts", "Savings Accounts"),
    "charge": ("charges", "Charge Definitions"),
    "glaccount": ("glaccounts", "General Ledger Accounts"),
    "journal": ("journalentries", "Journal Entries"),
    "report": ("reports", "Report Catalog"),
}

# key: (label, allowed target kind, command, transaction route, required payload keys, optional keys)
OPERATIONS = {
    "create_client": ("Create Client", "client", None, False,
        {"officeId", "firstname", "lastname", "active", "submittedOnDate", "dateFormat", "locale"}, {"externalId", "mobileNo"}),
    "create_group": ("Create Group", "group", None, False,
        {"officeId", "name", "active", "submittedOnDate", "dateFormat", "locale"}, {"externalId"}),
    "create_center": ("Create Center", "center", None, False,
        {"officeId", "name", "active", "dateFormat", "locale"}, {"externalId"}),
    "activate_client": ("Activate Client", "client", "activate", False,
        {"activationDate", "dateFormat", "locale"}, set()),
    "activate_group": ("Activate Group", "group", "activate", False,
        {"activationDate", "dateFormat", "locale"}, set()),
    "activate_center": ("Activate Center", "center", "activate", False,
        {"activationDate", "dateFormat", "locale"}, set()),
    "create_loan": ("Apply for Loan", "loan", None, False,
        {"clientId", "productId", "principal", "loanTermFrequency", "loanTermFrequencyType",
         "numberOfRepayments", "repaymentEvery", "repaymentFrequencyType", "interestRatePerPeriod",
         "amortizationType", "interestType", "interestCalculationPeriodType", "transactionProcessingStrategyCode",
         "expectedDisbursementDate", "submittedOnDate", "loanType", "dateFormat", "locale"}, {"externalId"}),
    "approve_loan": ("Approve Loan", "loan", "approve", False,
        {"approvedOnDate", "dateFormat", "locale"}, {"note"}),
    "disburse_loan": ("Disburse Loan", "loan", "disburse", False,
        {"actualDisbursementDate", "dateFormat", "locale"}, {"note", "paymentTypeId"}),
    "reject_loan": ("Reject Loan", "loan", "reject", False,
        {"rejectedOnDate", "dateFormat", "locale"}, {"note"}),
    "withdraw_loan": ("Withdraw Loan Application", "loan", "withdrawnByApplicant", False,
        {"withdrawnOnDate", "dateFormat", "locale"}, {"note"}),
    "repay_loan": ("Loan Repayment", "loan", "repayment", True,
        {"transactionDate", "transactionAmount", "dateFormat", "locale"}, {"note", "paymentTypeId"}),
    "writeoff_loan": ("Write Off Loan", "loan", "writeoff", True,
        {"transactionDate", "dateFormat", "locale"}, {"note"}),
    "close_loan": ("Close Loan", "loan", "close", True,
        {"transactionDate", "dateFormat", "locale"}, {"note"}),
    "create_savings": ("Apply for Savings Account", "savings", None, False,
        {"clientId", "productId", "submittedOnDate", "dateFormat", "locale"}, {"externalId"}),
    "approve_savings": ("Approve Savings Account", "savings", "approve", False,
        {"approvedOnDate", "dateFormat", "locale"}, {"note"}),
    "activate_savings": ("Activate Savings Account", "savings", "activate", False,
        {"activatedOnDate", "dateFormat", "locale"}, set()),
    "reject_savings": ("Reject Savings Account", "savings", "reject", False,
        {"rejectedOnDate", "dateFormat", "locale"}, {"note"}),
    "deposit_savings": ("Savings Deposit", "savings", "deposit", True,
        {"transactionDate", "transactionAmount", "dateFormat", "locale"}, {"note", "paymentTypeId"}),
    "withdraw_savings": ("Savings Withdrawal", "savings", "withdrawal", True,
        {"transactionDate", "transactionAmount", "dateFormat", "locale"}, {"note", "paymentTypeId"}),
    "close_savings": ("Close Savings Account", "savings", "close", False,
        {"closedOnDate", "dateFormat", "locale"}, {"note"}),
}


def build_request(operation, target_id, payload):
    """Reject forged routes and unexpected keys even if persisted data is corrupt."""
    if operation not in OPERATIONS:
        raise ValueError("Unsupported operation.")
    _, kind, command, transaction, required, optional = OPERATIONS[operation]
    if not isinstance(payload, dict) or not required <= payload.keys() or payload.keys() - required - optional:
        raise ValueError("Operation payload does not match its reviewed schema.")
    creating = operation.startswith("create_")
    if creating and target_id:
        raise ValueError("Create operations cannot target an existing record.")
    if not creating and (not isinstance(target_id, int) or isinstance(target_id, bool) or target_id <= 0):
        raise ValueError("An existing remote record is required.")
    if payload.get("locale") != "en" or payload.get("dateFormat") != "yyyy-MM-dd":
        raise ValueError("Unsupported date format or locale.")
    for key, value in payload.items():
        if key.endswith("Date"):
            date.fromisoformat(value)
        if key.endswith("Id") and key != "externalId":
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError("Remote identifiers must be positive integers.")
        if key in {"principal", "transactionAmount"}:
            try:
                amount = Decimal(str(value))
            except InvalidOperation as exc:
                raise ValueError("Invalid amount.") from exc
            if not amount.is_finite() or amount <= 0:
                raise ValueError("Amount must be positive and finite.")
    path = RESOURCES[kind][0]
    if target_id:
        path += f"/{target_id}"
    if transaction:
        path += "/transactions"
    return path, {"command": command} if command else {}
