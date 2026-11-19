"""Compile a pinned Fineract OpenAPI document into a constrained native-workspace catalog.

Input is a local, public API definition, never business observations or credentials.
Unsupported/untyped contracts remain visible with an explicit blocking reason.
"""
import argparse
import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path


from command_contracts import command_variants


def compile_catalog(spec):
    schemas = json.loads(json.dumps(spec.get("components", {}).get("schemas", {})))
    # Jersey's generated schema describes its Java MIME wrapper rather than the
    # uploaded bytes. Mifos document dialogs submit this part as a File.
    if "FormDataBodyPart" in schemas:
        schemas["FormDataBodyPart"] = {"type": "string", "format": "binary",
            "description": "Protected file part of a multipart request."}
    # DateParam wraps a query string in Java; getDate() parses that string
    # with the accompanying dateFormat/locale, rather than accepting an object.
    if "DateParam" in schemas:
        schemas["DateParam"] = {"type": "string", "format": "date"}
    # Mifos loan-product accounting submits IDs. The generated schema also
    # includes response-side charge/GL projections with recursive option lists.
    # See loan-product-accounting-step.component.ts at the pinned source revision.
    if "LoanProductChargeToGLAccountMapper" in schemas:
        schemas["LoanProductChargeToGLAccountMapper"] = {"type": "object",
            "required": ["chargeId", "incomeAccountId"], "properties": {
                "chargeId": {"type": "integer", "minimum": 1},
                "incomeAccountId": {"type": "integer", "minimum": 1}}}
    def normalize(schema):
        if not isinstance(schema, dict):
            return schema
        schema = {key: value for key, value in schema.items() if key not in {"example", "examples"}}
        if "properties" in schema:
            schema["properties"] = {name: dict(normalize(child), **({"x-mfierp-secret": True}
                if child.get("type") not in {"integer", "number", "boolean"} and not child.get("enum")
                and re.search(r"password|secret|credential|token|privateKey|apiKey", name, re.I) else {}))
                for name, child in schema["properties"].items()}
        if "items" in schema:
            schema["items"] = normalize(schema["items"])
        return schema
    schemas = {name: normalize(schema) for name, schema in schemas.items()}
    capabilities = []

    def inspect(schema, seen=()):
        if "$ref" in schema:
            name = schema["$ref"].rsplit("/", 1)[-1]
            if name in seen:
                return "Recursive request schema needs a dedicated form."
            return inspect({**schemas.get(name, {}), **{key: value for key, value in schema.items() if key != "$ref"}}, (*seen, name))
        if any(key in schema for key in ("oneOf", "anyOf", "allOf")):
            return "Polymorphic request schema needs an explicit form contract."
        kind = schema.get("type", "object" if "properties" in schema else "")
        if schema.get("x-mfierp-secret") and kind != "string":
            return "Structured credential settings need a dedicated secret-binding contract."
        if kind == "object":
            if not schema.get("properties"):
                return "Request object has no declared fields; a reviewed schema is required."
            for _name, child in schema["properties"].items():
                if child.get("readOnly"):
                    continue
                reason = inspect(child, seen)
                if reason:
                    return reason
        elif kind == "array":
            return inspect(schema.get("items", {}), seen)
        elif kind not in {"string", "number", "integer", "boolean"}:
            return "Untyped request field needs a reviewed schema."
        return ""

    def contains_secret(schema, seen=()):
        if not schema:
            return False
        if schema.get("x-mfierp-secret"):
            return True
        if "$ref" in schema:
            name = schema["$ref"].rsplit("/", 1)[-1]
            return name not in seen and contains_secret(schemas.get(name, {}), (*seen, name))
        return any(contains_secret(child, seen) for child in schema.get("properties", {}).values()) or contains_secret(schema.get("items"), seen)

    for path, item in sorted(spec["paths"].items()):
        for method, operation in sorted(item.items()):
            if method not in {"get", "post", "put", "delete", "patch"}:
                continue
            key = method + "_" + operation.get("operationId", hashlib.sha256(path.encode()).hexdigest()[:12])
            parameters = [*item.get("parameters", []), *operation.get("parameters", [])]
            parameters = [p for p in parameters if p.get("in") in {"path", "query"}]
            parameters = [{**p, "schema": schemas["DateParam"]} if p.get("schema", {}).get("$ref") == "#/components/schemas/DateParam" else p for p in parameters]
            blocked = ""
            if not path.startswith(("/v1/", "/v2/")):
                blocked = "This contract is outside the supported Fineract v1/v2 APIs."
            if any(part in path.lower() for part in ("authentication", "/self/", "/twofactor", "/password/", "/oauth")):
                blocked = "Human authentication/session workflow requires a separate identity contract."
            for param in parameters:
                if param["name"] == "command":
                    options = param.get("schema", {}).get("enum")
                    if options:
                        param = dict(param, schema={**param.get("schema", {}), "enum": options})
                        parameters = [param if p["name"] == "command" else p for p in parameters]
                    else:
                        blocked = blocked or "Command variants need source-reviewed schemas before execution."
            content = operation.get("requestBody", {}).get("content", {})
            media_type = "application/json" if "application/json" in content else "multipart/form-data" if "multipart/form-data" in content else ""
            body = normalize(content.get(media_type, {}).get("schema"))
            if content and body is None:
                blocked = blocked or "This request uses a non-JSON upload/body contract."
            if body is not None:
                blocked = blocked or inspect(body)
                if body.get("type") == "string" and body.get("format") not in {"binary", "byte"}:
                    blocked = blocked or "Opaque JSON request body needs a source-reviewed field schema."
            if any(p.get("schema", {}).get("type") not in {"string", "integer", "number", "boolean", "array"} for p in parameters):
                blocked = blocked or "A parameter needs an explicit type contract."
            capabilities.append({"key": key, "name": operation.get("summary") or operation.get("operationId") or path,
                "category": (operation.get("tags") or ["Other"])[0], "method": method.upper(), "path": path,
                "api_version": path.split("/")[1],
                "description": operation.get("description", ""), "parameters": parameters, "body": body,
                "media_type": media_type,
                "body_required": operation.get("requestBody", {}).get("required", False),
                "blocked": blocked, "admin_only": contains_secret(body) or bool(re.search(
                    r"/(users|roles|permissions|configuration|passwordpreferences|hooks|jobs|scheduler|datatables|codes|businessdate|cache|accountnumberformats|loanproducts|savingsproducts|fixeddepositproducts|recurringdepositproducts|shareproducts|shareproduct|glaccounts|journalentries|glclosures|provisioningcriteria|reports)(/|$)", path, re.I)),
                "source_operation": operation.get("operationId")})
    # Mifos createLoansAccount() posts without a command. Keep this distinct
    # from the unresolved calculation/other command variants at the same URL.
    loan = deepcopy(next(c for c in capabilities if c["method"] == "POST" and c["path"] == "/v1/loans"))
    loan_body = deepcopy(schemas["PostLoansRequest"])
    loan_body["properties"].pop("datatables", None)
    loan.update(key=loan["key"] + "__application", name="Loans: submit application",
        parameters=[p for p in loan["parameters"] if p["name"] != "command"],
        body=loan_body, blocked=inspect(loan_body), excluded_fields=["datatables"],
        description="Submit a loan application using the declared fields. Tenant-defined datatables are excluded and require a separate reviewed contract. Fineract validates product and borrower rules.",
        source_service="https://github.com/nandahtoon/Mifosx-web-app/blob/34c7f278861ef25052f2e00d106d8527f5d270d3/src/app/loans/loans.service.ts#L546")
    capabilities.append(loan)
    journal = deepcopy(next(c for c in capabilities if c["method"] == "POST" and c["path"] == "/v1/journalentries"))
    journal.update(key=journal["key"] + "__create", name="Accounting: create journal entry",
        parameters=[p for p in journal["parameters"] if p["name"] != "command"],
        blocked=inspect(journal["body"]) if journal["body"] else "Missing journal schema.",
        source_service="https://github.com/nandahtoon/Mifosx-web-app/blob/34c7f278861ef25052f2e00d106d8527f5d270d3/src/app/accounting/accounting.service.ts")
    capabilities.append(journal)
    reschedules = deepcopy(next(c for c in capabilities if c["method"] == "GET" and c["path"] == "/v1/rescheduleloans"))
    reschedules.update(key=reschedules["key"] + "__list", name="Loan rescheduling: list requests",
        parameters=[p for p in reschedules["parameters"] if p["name"] != "command"], blocked="",
        context_resource="loans", context_fields={"loanId": "query"},
        source_service="https://github.com/nandahtoon/Mifosx-web-app/blob/34c7f278861ef25052f2e00d106d8527f5d270d3/src/app/loans/loans.service.ts#L480")
    capabilities.append(reschedules)
    capabilities.extend(command_variants(capabilities))
    keys = [item["key"] for item in capabilities]
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate operation identifiers in source contract.")
    return {"schema_version": 1, "api_version": spec["info"]["version"],
        "source_sha256": hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest(),
        "license": "API metadata derived from Apache Fineract, Apache-2.0; no server or web application code vendored.",
        "capabilities": capabilities, "schemas": schemas}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("destination")
    args = parser.parse_args()
    catalog = compile_catalog(json.loads(Path(args.source).read_text(encoding="utf-8")))
    Path(args.destination).write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(len(catalog["capabilities"]), "operations;", sum(not c["blocked"] for c in catalog["capabilities"]), "typed form contracts")
