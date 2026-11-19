# SPDX-License-Identifier: LGPL-3.0-or-later
"""Server-owned OpenAPI contracts for the native extended operations workspace."""
import hashlib
import json
import math
import re
import os
import hmac
from datetime import date
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote


@lru_cache(maxsize=1)
def catalog():
    return json.loads(Path(__file__).with_name("catalog.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def capabilities():
    return {item["key"]: item for item in catalog()["capabilities"]}


def specification(key):
    if key not in capabilities():
        raise ValueError("Unknown workspace operation.")
    return capabilities()[key]


@lru_cache(maxsize=1)
def catalog_fingerprint():
    return hashlib.sha256(json.dumps(catalog(), sort_keys=True).encode()).hexdigest()


def contract_digest(key):
    return hashlib.sha256((catalog_fingerprint() + ":" + key).encode()).hexdigest()


def resolve(schema):
    seen = set()
    overrides = {}
    while "$ref" in schema:
        overrides.update({key: value for key, value in schema.items() if key != "$ref"})
        name = schema["$ref"].rsplit("/", 1)[-1]
        if name in seen or name not in catalog()["schemas"]:
            raise ValueError("Unresolvable contract reference.")
        seen.add(name)
        schema = catalog()["schemas"][name]
    return {**schema, **overrides}


def value_type(schema, name=""):
    schema = resolve(schema)
    if schema.get("x-mfierp-secret"):
        return "secret"
    if schema.get("format") in {"binary", "byte"}:
        return "binary"
    kind = schema.get("type", "object" if "properties" in schema else "")
    if kind == "string" and (schema.get("format") == "date" or re.search(r"(?:Date|dateOfBirth)$", name)):
        return "date"
    return kind


def validate(value, schema, label="value", depth=0, allow_staged=False):
    if depth > 8:
        raise ValueError("Request nesting exceeds the reviewed limit.")
    schema = resolve(schema)
    if schema.get("x-mfierp-secret"):
        if not isinstance(value, dict) or set(value) != {"environment", "binding", "context"}:
            raise ValueError("Credentials must use a bound deployment secret reference.")
        if not re.fullmatch(r"MFIERP_WORKFLOW_SECRET_[A-Z0-9_]{1,80}", value["environment"]) or value["environment"] == "MFIERP_SECRET_BINDING_KEY":
            raise ValueError("Invalid deployment secret reference.")
        if not re.fullmatch(r"[a-f0-9]{64}", value["binding"]) or not isinstance(value["context"], str) or len(value["context"]) > 256:
            raise ValueError("Invalid protected secret binding.")
        return
    if schema.get("format") in {"binary", "byte"}:
        if not isinstance(value, dict) or set(value) != {"storage", "id", "sha256", "name"}:
            raise ValueError("Uploads must use a protected file reference.")
        if value["storage"] not in ({"command", "staged"} if allow_staged else {"command"}):
            raise ValueError("Unbound upload cannot be dispatched.")
        if not isinstance(value["id"], int) or value["id"] <= 0 or not re.fullmatch(r"[a-f0-9]{64}", value["sha256"]):
            raise ValueError("Invalid protected file reference.")
        if not isinstance(value["name"], str) or any(char in value["name"] for char in "/\\\r\n"):
            raise ValueError("Invalid upload name.")
        return
    if value is None and schema.get("nullable"):
        return
    kind = schema.get("type", "object" if "properties" in schema else "")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{label}: choose a declared option.")
    if kind == "object":
        if not isinstance(value, dict):
            raise ValueError(f"{label}: expected a structured object.")
        props = schema.get("properties", {})
        if value.keys() - props.keys():
            raise ValueError(f"{label}: undeclared fields are prohibited.")
        if set(schema.get("required", [])) - value.keys():
            raise ValueError(f"{label}: required fields are missing.")
        for key, child in value.items():
            if props[key].get("readOnly"):
                raise ValueError(f"{label}: response-only field is prohibited.")
            validate(child, props[key], key, depth + 1, allow_staged)
    elif kind == "array":
        if not isinstance(value, list) or len(value) > min(schema.get("maxItems", 100), 100):
            raise ValueError(f"{label}: expected a list of at most 100 items.")
        if len(value) < schema.get("minItems", 0):
            raise ValueError(f"{label}: more list items are required.")
        for item in value:
            validate(item, schema.get("items", {}), label, depth + 1, allow_staged)
    elif kind in {"number", "integer"}:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"{label}: expected a finite number.")
        if kind == "integer" and not isinstance(value, int):
            raise ValueError(f"{label}: expected an integer.")
        if value < schema.get("minimum", -math.inf) or value > schema.get("maximum", math.inf):
            raise ValueError(f"{label}: number is outside the contract range.")
        for bound, inclusive, comparison in [("exclusiveMinimum", "minimum", lambda left, right: left <= right),
                ("exclusiveMaximum", "maximum", lambda left, right: left >= right)]:
            constraint = schema.get(bound)
            if isinstance(constraint, bool):
                if constraint and inclusive in schema and comparison(value, schema[inclusive]):
                    raise ValueError(f"{label}: number is outside the exclusive bounds.")
            elif constraint is not None and comparison(value, constraint):
                raise ValueError(f"{label}: number is outside the exclusive bounds.")
    elif kind == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"{label}: expected true or false.")
    elif kind == "string":
        if not isinstance(value, str) or len(value) > min(schema.get("maxLength", 10000), 10000):
            raise ValueError(f"{label}: expected bounded text.")
        if len(value) < schema.get("minLength", 0):
            raise ValueError(f"{label}: text is too short.")
        if schema.get("pattern") and not re.search(schema["pattern"], value):
            raise ValueError(f"{label}: text does not match the declared format.")
        if schema.get("format") == "date" or (label.endswith("Date") and value):
            date.fromisoformat(value)
    else:
        raise ValueError(f"{label}: untyped contracts cannot be executed.")


def build_request(key, envelope, *, allow_staged=False):
    spec = specification(key)
    if spec["blocked"]:
        raise ValueError(spec["blocked"])
    if not isinstance(envelope, dict) or set(envelope) != {"contract_digest", "path", "query", "body"}:
        raise ValueError("Malformed workspace request.")
    if envelope["contract_digest"] != contract_digest(key):
        raise ValueError("The source contract changed after this request was reviewed.")
    path_values, query = envelope["path"], envelope["query"]
    if not isinstance(path_values, dict) or not isinstance(query, dict):
        raise ValueError("Malformed request parameters.")
    for location, values in [("path", path_values), ("query", query)]:
        definitions = {p["name"]: p for p in spec["parameters"] if p["in"] == location}
        if values.keys() - definitions.keys():
            raise ValueError("Undeclared request parameter.")
        for name, param in definitions.items():
            if name not in values:
                if param.get("required"):
                    raise ValueError(f"{name}: required parameter is missing.")
                continue
            validate(values[name], param["schema"], name)
    version = spec.get("api_version", "v1")
    if version not in {"v1", "v2"} or not spec["path"].startswith(f"/{version}/"):
        raise ValueError("Unsupported versioned API contract.")
    path = spec["path"].removeprefix(f"/{version}/")
    for name, value in path_values.items():
        text = str(value)
        if not text or text in {".", ".."} or any(char in text for char in "/\\?#\r\n"):
            raise ValueError("Invalid resource identifier.")
        path = path.replace("{" + name + "}", quote(text, safe=""))
    if "{" in path or "}" in path or path.startswith("/"):
        raise ValueError("Unresolved request route.")
    body = envelope["body"]
    if spec["body"] is not None:
        if body is None and spec["body_required"]:
            raise ValueError("Request details are required.")
        if body is not None:
            validate(body, spec["body"], "body", allow_staged=allow_staged)
    elif body is not None:
        raise ValueError("This operation does not accept request details.")
    if "limit" in query and (not isinstance(query["limit"], int) or not 1 <= query["limit"] <= 1000):
        raise ValueError("Page size must be between 1 and 1000.")
    if "offset" in query and query["offset"] < 0:
        raise ValueError("Page offset cannot be negative.")
    if len(json.dumps(envelope)) > 512 * 1024:
        raise ValueError("Request exceeds the reviewed size limit.")
    return spec["method"], path, query, body


def map_uploads(value, schema, callback):
    schema = resolve(schema)
    if schema.get("format") in {"binary", "byte"}:
        return callback(value, schema)
    if isinstance(value, dict) and (schema.get("type") == "object" or "properties" in schema):
        return {key: map_uploads(child, schema["properties"][key], callback) for key, child in value.items()}
    if isinstance(value, list) and schema.get("type") == "array":
        return [map_uploads(child, schema["items"], callback) for child in value]
    return value


def bind_secret(reference, context):
    if not re.fullmatch(r"MFIERP_WORKFLOW_SECRET_[A-Z0-9_]{1,80}", reference or "") or reference == "MFIERP_SECRET_BINDING_KEY":
        raise ValueError("Use a dedicated MFIERP_WORKFLOW_SECRET_ deployment secret reference.")
    signing_key = os.environ.get("MFIERP_SECRET_BINDING_KEY", "")
    value = os.environ.get(reference)
    if len(signing_key) < 32 or not value or len(value) > 10000:
        raise ValueError("Configure the protected secret and a signing key of at least 32 characters in the deployment.")
    message = json.dumps([reference, context, value], ensure_ascii=False, separators=(",", ":")).encode()
    return {"environment": reference, "context": context,
        "binding": hmac.new(signing_key.encode(), message, hashlib.sha256).hexdigest()}


def reveal_secret(marker):
    expected = bind_secret(marker["environment"], marker["context"])
    if not hmac.compare_digest(expected["binding"], marker["binding"]):
        raise ValueError("The deployment secret changed after this request was reviewed.")
    return os.environ[marker["environment"]]


def map_secrets(value, schema):
    schema = resolve(schema)
    if schema.get("x-mfierp-secret"):
        return reveal_secret(value)
    if isinstance(value, dict) and (schema.get("type") == "object" or "properties" in schema):
        return {key: map_secrets(child, schema["properties"][key]) for key, child in value.items()}
    if isinstance(value, list) and schema.get("type") == "array":
        return [map_secrets(child, schema["items"]) for child in value]
    return value
