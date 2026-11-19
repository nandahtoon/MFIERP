"""Source-reviewed command variants for APIs whose OpenAPI body is representative.

These declarations describe transmitted fields, not financial calculations. Source
paths are pinned by SOURCE_REVISION; adding a command requires reviewing submit().
"""
from copy import deepcopy

SOURCE_REVISION = "34c7f278861ef25052f2e00d106d8527f5d270d3"
SOURCE_ROOT = f"https://github.com/nandahtoon/Mifosx-web-app/blob/{SOURCE_REVISION}/src/app/"


def command_variants(capabilities):
    variants = []

    def add(path, command, area, component, fields, required=(), dates=True, fixed_path=None):
        base = next(c for c in capabilities if c["method"] == "POST" and c["path"] == path)
        entry = deepcopy(base)
        entry.update(key=base["key"] + "__" + command, name=f"{area}: {command}", blocked="",
            description=f"Source-reviewed {command} command. Fineract validates eligibility, amounts and state transitions.",
            source_form=SOURCE_ROOT + component, source_revision=SOURCE_REVISION, body_required=True)
        params = [p for p in entry["parameters"] if p["name"] != "command"]
        for param in params:
            if param["in"] == "path" and param["name"] in (fixed_path or {}):
                value = fixed_path[param["name"]]
                param["schema"] = {"type": "string", "enum": [value], "default": value}
        params.append({"name": "command", "in": "query", "required": True,
            "schema": {"type": "string", "enum": [command], "default": command}})
        entry["parameters"] = params
        properties = {}
        for name, kind in fields.items():
            properties[name] = {"type": kind}
            if kind == "integer" and name.endswith("Id"):
                properties[name]["minimum"] = 1
            if name.lower().endswith("date"):
                properties[name]["format"] = "date"
        if dates:
            properties.update(dateFormat={"type": "string", "enum": ["yyyy-MM-dd"]}, locale={"type": "string", "enum": ["en"]})
        entry["body"] = {"type": "object", "properties": properties, "required": list(required)}
        variants.append(entry)
        return entry

    client = "clients/clients-view/client-actions/"
    for command, component, fields, required, dates in [
        ("activate", "activate-client", {"activationDate": "string"}, ["activationDate"], True),
        ("reactivate", "reactivate-client", {"reactivationDate": "string"}, ["reactivationDate"], True),
        ("close", "close-client", {"closureDate": "string", "closureReasonId": "integer"}, ["closureDate", "closureReasonId"], True),
        ("reject", "reject-client", {"rejectionDate": "string", "rejectionReasonId": "integer"}, ["rejectionDate", "rejectionReasonId"], True),
        ("withdraw", "withdraw-client", {"withdrawalDate": "string", "withdrawalReasonId": "integer"}, ["withdrawalDate", "withdrawalReasonId"], True),
        ("undoRejection", "undo-client-rejection", {"reopenedDate": "string"}, ["reopenedDate"], True),
        ("assignStaff", "client-assign-staff", {"staffId": "integer"}, ["staffId"], False),
        ("updateSavingsAccount", "update-client-savings-account", {"savingsAccountId": "integer"}, ["savingsAccountId"], False),
        ("proposeTransfer", "transfer-client", {"destinationOfficeId": "integer", "transferDate": "string", "note": "string"}, ["destinationOfficeId", "transferDate"], True),
        ("acceptTransfer", "accept-client-transfer", {"note": "string"}, [], False),
        ("rejectTransfer", "reject-client-transfer", {"note": "string"}, [], False),
        ("withdrawTransfer", "undo-client-transfer", {"note": "string"}, [], False),
    ]:
        add("/v1/clients/{clientId}", command, "Clients", f"{client}{component}/{component}.component.ts", fields, required, dates)

    loan = "loans/loans-view/loan-account-actions/"
    for command, component, fields, required in [
        ("approve", "approve-loan", {"approvedOnDate": "string", "expectedDisbursementDate": "string", "approvedLoanAmount": "number", "note": "string"}, ["approvedOnDate"]),
        ("reject", "reject-loan", {"rejectedOnDate": "string", "note": "string"}, ["rejectedOnDate"]),
        ("withdrawnByApplicant", "withdrawn-by-client", {"withdrawnOnDate": "string"}, ["withdrawnOnDate"]),
        ("disbursetosavings", "disburse-to-savings-account", {"actualDisbursementDate": "string", "transactionAmount": "number", "fixedEmiAmount": "number", "note": "string"}, ["actualDisbursementDate"]),
        ("assignLoanOfficer", "assign-loan-officer", {"toLoanOfficerId": "integer", "fromLoanOfficerId": "integer", "assignmentDate": "string"}, ["toLoanOfficerId", "assignmentDate"]),
        ("undoapproval", "undo-approval", {"note": "string"}, []),
        ("undodisbursal", "undo-disbursal", {"note": "string"}, []),
        ("undolastdisbursal", "undo-disbursal", {"note": "string"}, []),
    ]:
        add("/v1/loans/{loanId}", command, "Loans", f"{loan}{component}/{component}.component.ts", fields, required,
            dates=command not in {"undoapproval", "undodisbursal", "undolastdisbursal"})

    for command, component, fields, required in [
        ("close", "loans-account-close", {"transactionDate": "string", "note": "string"}, ["transactionDate"]),
        ("close-rescheduled", "close-as-rescheduled", {"transactionDate": "string", "note": "string"}, ["transactionDate"]),
        ("waiveinterest", "waive-interest", {"transactionDate": "string", "transactionAmount": "number", "note": "string"}, ["transactionDate", "transactionAmount"]),
        ("undowriteoff", "undo-write-off", {"transactionDate": "string", "transactionAmount": "number", "note": "string"}, ["transactionDate", "transactionAmount"]),
        ("charge-off", "charge-off", {"transactionDate": "string"}, ["transactionDate"]),
        ("recoverypayment", "recovery-repayment", {"transactionDate": "string", "transactionAmount": "number", "externalId": "string", "paymentTypeId": "integer", "note": "string",
            "accountNumber": "string", "checkNumber": "string", "routingCode": "string", "receiptNumber": "string", "bankNumber": "string"}, ["transactionDate", "transactionAmount"]),
    ]:
        add("/v1/loans/{loanId}/transactions", command, "Loans", f"{loan}{component}/{component}.component.ts", fields, required)

    for resource, prefix, area in [
        ("savingsaccounts/{accountId}", "savings/saving-account-actions/", "Savings"),
        ("fixeddepositaccounts/{accountId}", "deposits/fixed-deposits/fixed-deposits-account-actions/", "Fixed deposits"),
        ("recurringdepositaccounts/{accountId}", "deposits/recurring-deposits/recurring-deposits-account-actions/", "Recurring deposits"),
    ]:
        suffix = {"Savings": "savings-account", "Fixed deposits": "fixed-deposits-account", "Recurring deposits": "recurring-deposits-account"}[area]
        for command, stem, date in [("approve", "approve", "approvedOnDate"), ("reject", "reject", "rejectedOnDate"),
                ("withdrawnByApplicant", "withdraw-by-client", "withdrawnOnDate")]:
            component = f"{stem}-{suffix}"
            add("/v1/" + resource, command, area, f"{prefix}{component}/{component}.component.ts",
                {date: "string", "note": "string"}, [date])
    prefix = "savings/saving-account-actions/"
    for command, component, fields, required in [
        ("activate", "activate-savings-account", {"activatedOnDate": "string"}, ["activatedOnDate"]),
        ("undoapproval", "undo-approval-savings-account", {"note": "string"}, []),
        ("assignSavingsOfficer", "savings-account-assign-staff", {"toSavingsOfficerId": "integer", "assignmentDate": "string"}, ["toSavingsOfficerId", "assignmentDate"]),
        ("unassignSavingsOfficer", "savings-account-unassign-staff", {"unassignedDate": "string"}, ["unassignedDate"]),
        ("close", "close-savings-account", {"closedOnDate": "string", "withdrawBalance": "boolean", "postInterestValidationOnClosure": "boolean", "note": "string"}, ["closedOnDate"]),
    ]:
        add("/v1/savingsaccounts/{accountId}", command, "Savings", f"{prefix}{component}/{component}.component.ts", fields, required,
            dates=command != "undoapproval")
    for command in ["block", "blockCredit", "blockDebit"]:
        add("/v1/savingsaccounts/{accountId}", command, "Savings", f"{prefix}manage-savings-account/manage-savings-account.component.ts",
            {"reasonForBlock": "string"}, ["reasonForBlock"], dates=False)
    payment_fields = {"transactionDate": "string", "transactionAmount": "number", "paymentTypeId": "integer", "note": "string",
        "accountNumber": "string", "checkNumber": "string", "routingCode": "string", "receiptNumber": "string", "bankNumber": "string"}
    for command in ["deposit", "withdrawal"]:
        add("/v1/savingsaccounts/{savingsId}/transactions", command, "Savings", f"{prefix}savings-account-transactions/savings-account-transactions.component.ts",
            payment_fields, ["transactionDate", "transactionAmount"])
    add("/v1/savingsaccounts/{savingsId}/transactions", "holdAmount", "Savings", f"{prefix}manage-savings-account/manage-savings-account.component.ts",
        {"transactionDate": "string", "transactionAmount": "number", "reasonForBlock": "string"}, ["transactionDate", "transactionAmount"])
    add("/v1/savingsaccounts/{savingsId}/transactions", "postInterestAsOn", "Savings", f"{prefix}post-interest-as-on-savings-account/post-interest-as-on-savings-account.component.ts",
        {"transactionDate": "string"}, ["transactionDate"])
    for deposit, area in [("fixed", "Fixed deposits"), ("recurring", "Recurring deposits")]:
        prefix = f"deposits/{deposit}-deposits/{deposit}-deposits-account-actions/"
        component = f"close-{deposit}-deposits-account"
        fields = {"closedOnDate": "string", "onAccountClosureId": "integer", "toSavingsAccountId": "integer", "transferDescription": "string"}
        fields.update({"note": "string"} if deposit == "fixed" else {"paymentTypeId": "integer"})
        add(f"/v1/{deposit}depositaccounts/{{accountId}}", "close", area, f"{prefix}{component}/{component}.component.ts", fields, ["closedOnDate", "onAccountClosureId"])
        component = "premature-close-fixed-deposits-account" if deposit == "fixed" else "premature-close-recurring-deposit-account"
        fields = {"closedOnDate": "string"}
        if deposit == "fixed":
            fields.update(onAccountClosureId="integer", toSavingsAccountId="integer", transferDescription="string", note="string")
        add(f"/v1/{deposit}depositaccounts/{{accountId}}", "prematureClose", area, f"{prefix}{component}/{component}.component.ts", fields, ["closedOnDate"])
    for resource in ["groups", "centers"]:
        singular = "group" if resource == "groups" else "center"
        prefix = f"{resource}/{resource}-view/{singular}-actions/"
        path = f"/v1/{resource}/{{{singular}Id}}"
        for command, component, fields, required in [
            ("activate", f"activate-{singular}", {"activationDate": "string"}, ["activationDate"]),
            ("close", f"close-{singular}", {"closureDate": "string", "closureReasonId": "integer"}, ["closureDate", "closureReasonId"]),
        ]:
            add(path, command, resource.capitalize(), f"{prefix}{component}/{component}.component.ts", fields, required)
    add("/v1/groups/{groupId}", "assignStaff", "Groups", "groups/groups-view/group-actions/group-assign-staff/group-assign-staff.component.ts",
        {"staffId": "integer"}, ["staffId"], dates=False)
    prefix = "shares/shares-account-actions/"
    for command, component, fields, required in [
        ("activate", "activate-shares-account", {"activatedDate": "string"}, ["activatedDate"]),
        ("approve", "approve-shares-account", {"approvedDate": "string", "note": "string"}, ["approvedDate"]),
        ("reject", "reject-shares-account", {"rejectedDate": "string", "note": "string"}, ["rejectedDate"]),
        ("close", "close-shares-account", {"closedDate": "string", "note": "string"}, ["closedDate"]),
        ("applyadditionalshares", "apply-shares", {"requestedDate": "string", "requestedShares": "number", "unitPrice": "number"}, ["requestedDate", "requestedShares", "unitPrice"]),
        ("redeemshares", "redeem-shares", {"requestedDate": "string", "requestedShares": "number", "unitPrice": "number"}, ["requestedDate", "requestedShares", "unitPrice"]),
        ("undoapproval", "undo-approval-shares-account", {}, []),
    ]:
        add("/v1/accounts/{type}/{accountId}", command, "Shares", f"{prefix}{component}/{component}.component.ts", fields, required,
            dates=command != "undoapproval", fixed_path={"type": "share"})
    for command in ["enable", "disable"]:
        entry = add("/v1/roles/{roleId}", command, "Role administration", "system/system.service.ts#L136",
            {}, dates=False)
        entry["admin_only"] = True
    for command in ["activate", "deactivate"]:
        entry = add("/v1/surveys/{id}", command, "Survey administration", "system/system.service.ts#L255",
            {}, dates=False)
        entry.update(body=None, body_required=False, admin_only=True)
    entry = add("/v1/jobs/{jobId}", "executeJob", "Job administration", "system/system.service.ts#L347", {}, dates=False)
    entry["admin_only"] = True
    entry["description"] += " This variant runs the job without custom parameters. Review job scope and effects before approval."
    return variants
