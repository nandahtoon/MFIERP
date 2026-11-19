# SPDX-License-Identifier: LGPL-3.0-or-later
"""Compile registered Fineract data tables into bounded, typed entry contracts.

Only server-fetched registration metadata is accepted by ORM callers. No schema,
SQL, path, command or arbitrary JSON field is supplied by the operator.
"""
import hashlib
import json
import re


APPLICATIONS = {
    "m_client": ("clients", "client_id"), "m_group": ("groups", "group_id"),
    "m_center": ("centers", "center_id"), "m_loan": ("loans", "loan_id"),
    "m_savings_account": ("savingsaccounts", "savings_account_id"),
    "m_office": ("offices", "office_id"), "m_product_loan": ("loanproducts", "product_loan_id"),
    "m_savings_product": ("savingsproducts", "savings_product_id"),
    "m_share_product": ("products", "share_product_id"),
}
SYSTEM_COLUMNS = {"id", "created_at", "updated_at", "createdby_id", "lastmodifiedby_id",
    "savings_transaction_id", *(item[1] for item in APPLICATIONS.values())}
ACTIONS = {"read": "GET", "create": "POST", "update": "PUT", "delete": "DELETE"}
ADMIN_APPLICATIONS = {"m_office", "m_product_loan", "m_savings_product", "m_share_product"}
IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_ -]{0,99}")


def identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value) or value != value.strip():
        raise ValueError("Unsupported data table or column identifier.")
    return value


def snapshot(metadata):
    if not isinstance(metadata, dict):
        raise ValueError("Invalid registered data table metadata.")
    name = identifier(metadata.get("registeredTableName"))
    application = metadata.get("applicationTableName")
    if application not in APPLICATIONS:
        raise ValueError("This application table needs a separately reviewed adapter.")
    columns = metadata.get("columnHeaderData")
    if not isinstance(columns, list) or not 1 <= len(columns) <= 100:
        raise ValueError("Data table metadata must declare 1 to 100 columns.")
    normalized = []
    for column in columns:
        if not isinstance(column, dict):
            raise ValueError("Invalid column metadata.")
        key = identifier(column.get("columnName"))
        if any(item["columnName"] == key for item in normalized):
            raise ValueError("Duplicate data table column.")
        flags = [column.get("isColumnPrimaryKey"), column.get("isColumnNullable")]
        if any(not isinstance(flag, bool) for flag in flags):
            raise ValueError("Column key and nullability metadata must be explicit.")
        length = column.get("columnLength", 0)
        if isinstance(length, bool) or not isinstance(length, int) or length < 0:
            raise ValueError("Invalid column length.")
        values = column.get("columnValues", [])
        if not isinstance(values, list) or len(values) > 1000:
            raise ValueError("Too many dropdown options.")
        choices = []
        for option in values:
            if not isinstance(option, dict) or type(option.get("id")) is not int or option["id"] <= 0:
                raise ValueError("Dropdown values must have positive integer IDs.")
            label = option.get("value", "")
            if not isinstance(label, str) or len(label) > 250 or option["id"] in [item["id"] for item in choices]:
                raise ValueError("Invalid or duplicate dropdown option.")
            choices.append({"id": option["id"], "value": label})
        normalized.append({"columnName": key, "columnType": str(column.get("columnType", ""))[:100],
            "columnDisplayType": str(column.get("columnDisplayType", ""))[:30], "columnLength": length,
            "isColumnPrimaryKey": flags[0], "isColumnNullable": flags[1],
            "columnValues": sorted(choices, key=lambda item: item["id"])})
    subtype = metadata.get("entitySubType")
    if subtype is not None and (not isinstance(subtype, str) or len(subtype) > 100):
        raise ValueError("Invalid entity subtype.")
    return {"registeredTableName": name, "applicationTableName": application, "entitySubType": subtype,
        "columnHeaderData": sorted(normalized, key=lambda item: item["columnName"])}


def compile_table(metadata):
    data = snapshot(metadata)
    resource, foreign_key = APPLICATIONS[data["applicationTableName"]]
    columns = {column["columnName"]: column for column in data["columnHeaderData"]}
    keys = {name for name, column in columns.items() if column["isColumnPrimaryKey"]}
    if foreign_key not in columns or keys not in ({foreign_key}, {"id"}):
        raise ValueError("Unsupported primary/parent key layout.")
    if any(columns[name]["columnDisplayType"] != "INTEGER" or columns[name]["isColumnNullable"] for name in keys | {foreign_key}):
        raise ValueError("Data table parent and primary keys must be non-null integers.")
    multi = keys == {"id"}
    properties, required = {}, []
    for name, column in columns.items():
        if name in SYSTEM_COLUMNS:
            continue
        if name in {"locale", "dateFormat"} or re.search(r"password|secret|token|credential|api.?key", name, re.I):
            raise ValueError("Reserved or credential-bearing columns need a separate adapter.")
        display = column["columnDisplayType"]
        kind = {"INTEGER": "integer", "DECIMAL": "number", "STRING": "string", "TEXT": "string",
            "BOOLEAN": "boolean", "DATE": "string", "CODELOOKUP": "integer"}.get(display)
        if not kind or column["columnType"].lower() in {"json", "jsonb", "blob", "binary"}:
            raise ValueError("Unsupported column type; datetime, JSON and binary need a separate adapter.")
        schema = {"type": kind, "title": name}
        if kind == "string":
            schema["maxLength"] = min(column["columnLength"] or 10000, 10000)
        if display == "DATE":
            schema["format"] = "date"
        if display == "CODELOOKUP":
            if not column["columnValues"]:
                raise ValueError("Dropdown metadata has no reviewed options.")
            schema["enum"] = [option["id"] for option in column["columnValues"]]
            schema["description"] = "; ".join(f"{option['id']}: {option['value']}" for option in column["columnValues"])
        properties[name] = schema
        if not column["isColumnNullable"]:
            required.append(name)
    if not properties:
        raise ValueError("No supported editable columns were declared.")
    properties.update(locale={"type": "string", "enum": ["en"]}, dateFormat={"type": "string", "enum": ["yyyy-MM-dd"]})
    return {"metadata": data, "resource": resource, "multi_row": multi,
        "body": {"type": "object", "properties": properties, "required": required}}


def fingerprint(metadata):
    return hashlib.sha256(json.dumps(snapshot(metadata), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def specification(metadata, action):
    if action not in ACTIONS:
        raise ValueError("Choose a declared data table entry action.")
    compiled = compile_table(metadata)
    parameters = [{"name": "datatable", "in": "path", "required": True,
        "schema": {"type": "string", "enum": [compiled["metadata"]["registeredTableName"]]}},
        {"name": "apptableId", "in": "path", "required": True, "schema": {"type": "integer", "minimum": 1}}]
    path = "/v1/datatables/{datatable}/{apptableId}"
    if compiled["multi_row"] and action in {"update", "delete"}:
        path += "/{datatableId}"
        parameters.append({"name": "datatableId", "in": "path", "required": True, "schema": {"type": "integer", "minimum": 1}})
    if action == "read":
        parameters.append({"name": "genericResultSet", "in": "query", "required": True, "schema": {"type": "boolean", "enum": [True]}})
    return {"method": ACTIONS[action], "path": path, "api_version": "v1", "parameters": parameters,
        "body": compiled["body"] if action in {"create", "update"} else None,
        "body_required": action in {"create", "update"}, "blocked": "",
        "admin_only": compiled["metadata"]["applicationTableName"] in ADMIN_APPLICATIONS,
        "context_resource": compiled["resource"], "context_fields": {"apptableId": "path"}}


def project_rows(result, metadata):
    """Keep only declared columns in a bounded generic-result-set preview."""
    declared = {item["columnName"] for item in snapshot(metadata)["columnHeaderData"]}
    if not isinstance(result, dict) or not isinstance(result.get("columnHeaders"), list) or not isinstance(result.get("data"), list):
        raise ValueError("Expected the declared Fineract generic result set.")
    headers = [item.get("columnName") for item in result["columnHeaders"] if isinstance(item, dict)]
    if (any(not isinstance(header, str) for header in headers) or len(headers) != len(result["columnHeaders"])
            or len(headers) > 100 or len(set(headers)) != len(headers) or set(headers) - declared):
        raise ValueError("Data table response columns differ from the reviewed metadata.")
    rows = []
    for item in result["data"][:200]:
        values = item.get("row") if isinstance(item, dict) else None
        if not isinstance(values, list) or len(values) != len(headers):
            raise ValueError("Invalid data table row.")
        if any(isinstance(value, (dict, list)) or len(str(value)) > 10000 for value in values):
            raise ValueError("Unsupported data table response value.")
        rows.append(dict(zip(headers, values, strict=True)))
    return {"pageItems": rows, "truncated": len(result["data"]) > 200}
