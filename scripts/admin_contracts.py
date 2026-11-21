"""Reviewed administrative and standing-instruction wire contracts.

The callback belongs to command_contracts; these are declarations rather than a
second registry or a financial engine. Upstream references are pinned there.
"""
from copy import deepcopy

BACKEND_ROOT = "https://github.com/apache/fineract/blob/6a28754c6839fa64f5faf1873f9fcb52bc330fd9/"


def extend_admin_contracts(add):
    def positive_id():
        return {"type": "integer", "minimum": 1}

    def reviewed(entry, backend=None):
        for param in entry["parameters"]:
            if param["in"] == "path" and param["schema"].get("type") == "integer":
                param["schema"]["minimum"] = 1
        if backend:
            entry["source_backend"] = BACKEND_ROOT + backend
        return entry

    fields = {"priority": {"type": "integer", "minimum": 1, "maximum": 4},
        "status": {"type": "integer", "enum": [1, 2]}, "instructionType": {"type": "integer", "enum": [1, 2]},
        "amount": {"type": "number", "minimum": 0, "exclusiveMinimum": True}, "validFrom": {"type": "string", "format": "date"},
        "validTill": {"type": "string", "format": "date"}, "recurrenceType": {"type": "integer", "enum": [1, 2]},
        "recurrenceInterval": {"type": "integer", "minimum": 1}, "recurrenceFrequency": {"type": "integer", "minimum": 0, "maximum": 3},
        "recurrenceOnMonthDay": {"type": "string", "pattern": r"^(0[1-9]|[12][0-9]|3[01]) (January|February|March|April|May|June|July|August|September|October|November|December)$",
            "description": "Day and English month, for example 19 November. Fineract validates the calendar date."},
        "monthDayFormat": {"type": "string", "enum": ["dd MMMM"]}}
    reviewed(add("/v1/standinginstructions/{standingInstructionId}", "update", "Standing instructions",
        "account-transfers/edit-standing-instructions/edit-standing-instructions.component.ts", fields,
        ["priority", "status", "validFrom", "validTill", "recurrenceType"], method="PUT"),
        "fineract-account-transfer/src/main/java/org/apache/fineract/portfolio/account/data/request/StandingInstructionUpdateRequest.java")

    product_rows = {"type": "array", "minItems": 1, "maxItems": 100, "x-mfierp-unique-by": "id", "items": {
        "type": "object", "required": ["id"], "properties": {"id": positive_id(), "name": {"type": "string", "maxLength": 200},
            "includeInBorrowerCycle": {"type": "boolean"}}}}
    definition_rows = {"type": "array", "minItems": 1, "maxItems": 100, "x-mfierp-unique-by": "categoryId", "items": {
        "type": "object", "required": ["categoryId", "minAge", "maxAge", "provisioningPercentage", "liabilityAccount", "expenseAccount"],
        "x-mfierp-greater-than": [["maxAge", "minAge"]], "properties": {
            "categoryId": positive_id(), "categoryName": {"type": "string", "maxLength": 200},
            "minAge": {"type": "integer", "minimum": 0}, "maxAge": {"type": "integer", "minimum": 1},
            "provisioningPercentage": {"type": "number", "minimum": 0},
            "liabilityAccount": positive_id(), "expenseAccount": positive_id()}}}
    for method, path, suffix, component in [
        ("POST", "/v1/provisioningcriteria", "createCriteria", "create"),
        ("PUT", "/v1/provisioningcriteria/{criteriaId}", "updateCriteria", "edit"),
    ]:
        entry = add(path, None, "Provisioning criteria",
            f"organization/loan-provisioning-criteria/{component}-loan-provisioning-criteria/{component}-loan-provisioning-criteria.component.ts",
            {"criteriaName": {"type": "string", "minLength": 1, "maxLength": 200}, "loanProducts": deepcopy(product_rows),
                "definitions": deepcopy(definition_rows), "locale": {"type": "string", "enum": ["en"]}},
            ["criteriaName", "loanProducts", "definitions"], dates=False, method=method, suffix=suffix)
        reviewed(entry, "fineract-provider/src/main/java/org/apache/fineract/organisation/provisioning/serialization/ProvisioningCriteriaDefinitionJsonDeserializer.java")
        entry["admin_only"] = True
        entry["description"] += " Select explicit loan products and every required category from the remote template. Fineract calculates provisions and validates ledger accounts; no journals are created in Odoo."

    dividend = reviewed(add("/v1/shareproduct/{productId}/dividend", None, "Share dividends",
        "products/share-products/create-dividend/create-dividend.component.ts",
        {"dividendPeriodStartDate": "string", "dividendPeriodEndDate": "string",
            "dividendAmount": {"type": "number", "minimum": 0, "exclusiveMinimum": True}},
        ["dividendPeriodStartDate", "dividendPeriodEndDate", "dividendAmount"], suffix="createDividend"),
        "fineract-provider/src/main/java/org/apache/fineract/portfolio/shareproducts/api/ShareDividendApiResource.java")
    dividend.update(require_reconciliation=True, reconciliation_scope="dividend", capture_subresource=True)
    # The reviewed write service consumes the payout ID supplied by the handler;
    # it consumes no body values for approval. Do not duplicate editable IDs.
    dividend = reviewed(add("/v1/shareproduct/{productId}/dividend/{dividendId}", "approve", "Share dividends",
        "products/share-products/view-dividend/view-dividend.component.ts", {}, dates=False, method="PUT"),
        "fineract-provider/src/main/java/org/apache/fineract/portfolio/shareproducts/service/ShareProductWritePlatformServiceJpaRepositoryImpl.java")
    dividend.update(require_reconciliation=True, reconciliation_scope="dividend")
    dividend["description"] += " Approval changes the remote payout plan; it does not prove completed payments. Reconcile the plan and affected accounts."

    for command in ["start", "stop"]:
        entry = reviewed(add("/v1/scheduler", command, "Scheduler",
            "system/manage-jobs/scheduler-jobs/manage-scheduler-jobs.component.ts", {}, dates=False))
        entry["admin_only"] = True
        entry["reconciliation_without_resource"] = True
        entry["description"] += " Re-read scheduler status after dispatch and reconcile its outcome before confirming it."
