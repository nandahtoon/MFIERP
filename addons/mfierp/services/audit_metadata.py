# SPDX-License-Identifier: LGPL-3.0-or-later
"""Bounded metadata projection for audit and maker/checker responses.

Field names and primitive types are reviewed against Apache Fineract AuditData:
https://github.com/apache/fineract/blob/6a28754c6839fa64f5faf1873f9fcb52bc330fd9/
fineract-provider/src/main/java/org/apache/fineract/commands/data/AuditData.java

commandAsJson contains submitted command data. Never copy it, URL/IP fields,
unknown fields or nested values into the persisted projection.
"""

MAX_ROWS = 200
MAX_LABEL_LENGTH = 250
MAX_DATE_LENGTH = 1000
MAX_IDENTIFIER = (1 << 63) - 1

_IDENTIFIER_FIELDS = (
    "id", "resourceId", "subresourceId", "clientId", "loanId", "officeId", "groupId",
    "savingsAccountId", "productId", "submittedOfficeId", "submittedGroupId", "submittedClientId",
    "submittedLoanId", "submittedSavingsAccountId", "submittedProductId", "submittedResourceId",
    "submittedSubresourceId",
)
_TEXT_FIELDS = (
    "actionName", "entityName", "maker", "checker", "processingResult", "officeName",
    "loanAccountNo", "savingsAccountNo", "transactionId", "resourceExternalId", "subresourceExternalId",
    "loanExternalId", "submittedTransactionId", "submittedResourceExternalId", "submittedSubresourceExternalId",
    "submittedLoanExternalId",
)
_DATE_FIELDS = ("madeOnDate", "checkedOnDate")


def _integer(value, minimum, label):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= MAX_IDENTIFIER:
        raise ValueError(f"Invalid audit metadata {label}.")
    return value


def _row(data):
    if not isinstance(data, dict) or "id" not in data:
        raise ValueError("Audit metadata must contain an audit identifier.")
    result = {"id": _integer(data["id"], 1, "id")}
    for name in _IDENTIFIER_FIELDS:
        if name != "id" and name in data and data[name] is not None:
            result[name] = _integer(data[name], 1, name)
    for names, limit in [(_TEXT_FIELDS, MAX_LABEL_LENGTH), (_DATE_FIELDS, MAX_DATE_LENGTH)]:
        for name in names:
            if name in data and data[name] is not None:
                if not isinstance(data[name], str):
                    raise ValueError(f"Audit metadata {name} must be text.")
                result[name] = data[name][:limit]
    return result


def project_metadata(data):
    """Normalize one audit, a list, or a page to whitelisted scalar rows.

    Only the first 200 rows are inspected. Optional null metadata is omitted;
    unknown fields are ignored without traversing their values. The zero page
    count and false truncation flag remain meaningful, but identifiers are
    positive integers. Errors never interpolate values from the remote payload.
    """
    total = None
    if isinstance(data, dict) and "pageItems" in data:
        items = data["pageItems"]
        if "totalFilteredRecords" in data:
            total = _integer(data["totalFilteredRecords"], 0, "totalFilteredRecords")
    elif isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = [data]
    else:
        raise ValueError("Audit response must be an object, a list, or a page.")
    if not isinstance(items, list):
        raise ValueError("Audit pageItems must be a list.")
    result = {"pageItems": [_row(item) for item in items[:MAX_ROWS]], "truncated": len(items) > MAX_ROWS}
    if total is not None:
        result["totalFilteredRecords"] = total
    return result
