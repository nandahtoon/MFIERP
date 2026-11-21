"""Reviewed organization and savings wire contracts.

Only the declared frontend fields reach Fineract. Account eligibility, officer
assignment rules, holiday scheduling and withholding calculations remain remote.
"""

BACKEND_ROOT = "https://github.com/apache/fineract/blob/6a28754c6839fa64f5faf1873f9fcb52bc330fd9/"
FRONTEND_ROOT = "https://github.com/nandahtoon/Mifosx-web-app/blob/34c7f278861ef25052f2e00d106d8527f5d270d3/src/app/"


def extend_organization_contracts(add):
    def reviewed(entry, backend):
        for param in entry["parameters"]:
            if param["in"] == "path" and param["schema"].get("type") == "integer":
                param["schema"]["minimum"] = 1
        entry["source_backend"] = BACKEND_ROOT + backend
        return entry

    reassignment = reviewed(add("/v1/loans/loanreassignment", None, "Loan officers",
        "organization/bulk-loan-reassignmnet/bulk-loan-reassignmnet.component.ts#L141-L169",
        {"fromLoanOfficerId": {"type": "integer", "minimum": 1},
            "toLoanOfficerId": {"type": "integer", "minimum": 1}, "assignmentDate": "string",
            "loans": {"type": "array", "minItems": 1, "maxItems": 100, "uniqueItems": True,
                "items": {"type": "integer", "minimum": 1}}},
        ["fromLoanOfficerId", "toLoanOfficerId", "assignmentDate", "loans"], suffix="reassignLoans"),
        "fineract-provider/src/main/java/org/apache/fineract/portfolio/loanaccount/api/BulkLoansApiResource.java#L108-L117")
    reassignment.update(admin_only=True, require_reconciliation=True, reconciliation_scope="loan_reassignment")
    reassignment["body"]["x-mfierp-different-fields"] = [["fromLoanOfficerId", "toLoanOfficerId"]]
    reassignment["description"] += (
        " Select explicit loan IDs from the remote officer template. Fineract validates the officers and assignment date."
        " Reconcile the officer assignment of every selected loan before confirming completion."
    )

    holiday = reviewed(add("/v1/holidays/{holidayId}", "activate", "Holidays",
        "organization/holidays/view-holidays/view-holidays.component.ts#L81-L103", {}, dates=False),
        "fineract-provider/src/main/java/org/apache/fineract/organisation/holiday/api/HolidaysApiResource.java#L108-L126")
    holiday.update(body=None, body_required=False, admin_only=True,
        require_reconciliation=True, reconciliation_scope="holiday")
    holiday["source_service"] = FRONTEND_ROOT + "organization/organization.service.ts#L651-L658"
    holiday["description"] += (
        " Fineract activates the existing holiday without a request body."
        " Re-read the holiday and reconcile any affected loan schedules before confirming completion."
    )

    withholding = reviewed(add("/v1/savingsaccounts/{accountId}", "updateWithHoldTax", "Savings",
        "savings/savings-account-view/savings-account-view.component.ts#L340-L377",
        {"withHoldTax": "boolean"}, ["withHoldTax"], dates=False, method="PUT"),
        "fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/SavingsAccountsApiResource.java#L495-L507")
    withholding["source_service"] = FRONTEND_ROOT + "savings/savings.service.ts#L235-L237"
    withholding["description"] += (
        " Enable or disable withholding for the selected savings account."
        " Fineract validates account applicability and the tax group and owns all tax calculations and postings."
    )
