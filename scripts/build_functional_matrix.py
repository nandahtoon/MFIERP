# SPDX-License-Identifier: LGPL-3.0-or-later
"""Inventory pinned Mifos app source facts without asserting operator parity.

This offline extractor deliberately leaves every generated row NOT_MAPPED.
Finding a component, event or executable API contract does not establish its
business meaning, native Odoo implementation, edition support or live UAT.
Curated review evidence and owner-approved scope remain separate inputs.
"""
import argparse
import csv
import hashlib
import html
import json
import posixpath
import re
from collections import Counter, namedtuple
from datetime import datetime
from html.parser import HTMLParser
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path, PurePosixPath

# Load only this repository-owned sibling, independently of cwd and sys.path.
# Its validation functions are pure; importing it performs no download or writes.
_SOURCE_HELPER_SPEC = spec_from_file_location(
    "_mfierp_pinned_source", Path(__file__).resolve().with_name("fetch_mifos_source.py"))
_source_helper = module_from_spec(_SOURCE_HELPER_SPEC)
_SOURCE_HELPER_SPEC.loader.exec_module(_source_helper)

SOURCE_REPOSITORY = "nandahtoon/Mifosx-web-app"
SOURCE_REVISION = "34c7f278861ef25052f2e00d106d8527f5d270d3"
SOURCE_ROOT = f"https://github.com/{SOURCE_REPOSITORY}/blob/{SOURCE_REVISION}/"
EXTRACTOR_VERSION = "1"
SOURCE_SUFFIXES = (".ts", ".html", ".json", ".scss")

FIELDNAMES = (
    "id", "row_kind", "domain", "subdomain", "persona", "operator_goal", "mifos_menu_screen_action",
    "source_repository", "source_revision", "source_path", "source_line", "source_column", "source_url",
    "parent_ids", "source_expression", "source_conditionals", "extraction_evidence", "scope_review",
    "fineract_endpoint", "http_method", "fineract_command", "contract_candidate_keys", "contract_candidate_status",
    "schema_fields_conditionals", "required_tenant_product_role", "authorization_maker_checker",
    "remote_side_effects_ledger", "odoo_menu_model_form_flow", "upstream_source_gaps", "error_undo_reversal_paths",
    "negative_security_tests", "unit_test", "odoo_install_security_test", "browser_test",
    "authenticated_integration_test", "independent_review_reference", "live_uat_evidence_link",
    "semantic_mapping_evidence", "contract_review_evidence", "implementation_evidence", "edition_app_scope",
    "ce_test_evidence", "ee_test_evidence", "approved_scope_decision", "status", "blocker",
    "resolution_waiver_owner", "accepted_at", "acceptance_criteria",
)
STATUS_DEFINITIONS = {
    "NOT_MAPPED": "Extraction or an unresolved obligation only; no reviewed semantic mapping or completion inferred.",
    "SOURCE_MAPPED": "A reviewer explicitly mapped the operator goal and pinned source; no implementation/UAT inferred.",
    "CONTRACT_VERIFIED": "Reviewed source mapping and exact remote contract/permissions/effects are evidenced.",
    "IMPLEMENTED": "A reviewed native Odoo implementation is linked; tests and live UAT remain separate.",
    "LOCAL_TEST_PASS": "Exact-head local unit, Odoo installation/security and browser evidence is linked; no live UAT inferred.",
    "STAGING_UAT_PASS": "Authenticated synthetic staging integration/UAT and independent review are linked.",
    "OPERATOR_ACCEPTED": "The accountable owner accepted the verified workflow with an acceptance timestamp.",
    "NOT_APPLICABLE_APPROVED": "An explicit signed scope exclusion is linked, with owner and date; not a delivered feature.",
    "UPSTREAM_BLOCKED": "A reviewed upstream limitation and resolution owner are linked; absence of a catalog match is insufficient.",
    "RED_APPROVAL_BLOCKED": "A specific external/policy/financial approval blocks work; no approval inferred.",
}
_STATUS_GATES = {
    "SOURCE_MAPPED": ("semantic_mapping_evidence",),
    "CONTRACT_VERIFIED": ("semantic_mapping_evidence", "contract_review_evidence", "schema_fields_conditionals",
        "authorization_maker_checker", "remote_side_effects_ledger"),
    "IMPLEMENTED": ("semantic_mapping_evidence", "contract_review_evidence", "implementation_evidence",
        "odoo_menu_model_form_flow"),
    "LOCAL_TEST_PASS": ("semantic_mapping_evidence", "contract_review_evidence", "implementation_evidence",
        "unit_test", "odoo_install_security_test", "browser_test"),
    "STAGING_UAT_PASS": ("semantic_mapping_evidence", "contract_review_evidence", "implementation_evidence", "unit_test",
        "odoo_install_security_test", "browser_test", "authenticated_integration_test", "live_uat_evidence_link",
        "independent_review_reference"),
    "OPERATOR_ACCEPTED": ("semantic_mapping_evidence", "contract_review_evidence", "implementation_evidence", "unit_test",
        "odoo_install_security_test", "browser_test", "authenticated_integration_test", "live_uat_evidence_link",
        "independent_review_reference", "resolution_waiver_owner", "accepted_at", "approved_scope_decision"),
    "NOT_APPLICABLE_APPROVED": ("approved_scope_decision", "resolution_waiver_owner", "accepted_at"),
    "UPSTREAM_BLOCKED": ("upstream_source_gaps", "independent_review_reference", "blocker", "resolution_waiver_owner"),
    "RED_APPROVAL_BLOCKED": ("blocker", "resolution_waiver_owner"),
}
# Higher workflow states retain all earlier evidence gates. These check explicit
# references, not their truth: a reviewer still has to inspect the cited evidence.
_STATUS_ORDER = ("SOURCE_MAPPED", "CONTRACT_VERIFIED", "IMPLEMENTED", "LOCAL_TEST_PASS",
    "STAGING_UAT_PASS", "OPERATOR_ACCEPTED")
for _previous, _current in zip(_STATUS_ORDER[:-1], _STATUS_ORDER[1:], strict=True):
    _STATUS_GATES[_current] = tuple(dict.fromkeys(_STATUS_GATES[_previous] + _STATUS_GATES[_current]))
_STATUS_GATES["OPERATOR_ACCEPTED"] += ("required_tenant_product_role", "error_undo_reversal_paths",
    "negative_security_tests", "edition_app_scope", "ce_test_evidence", "ee_test_evidence")
_SOURCE_FACT_FIELDS = frozenset({"id", "row_kind", "source_repository", "source_revision", "source_path",
    "source_line", "source_column", "source_url", "source_expression", "source_conditionals", "parent_ids",
    "extraction_evidence"})
_HTTP_METHODS = {"get", "post", "put", "delete", "patch", "head", "options"}
_ATTRIBUTES = re.compile(r'''([^\s=/>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?''', re.DOTALL)
Token = namedtuple("Token", "kind value start end quote", defaults=("",))


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_id(row_kind, source_path, line="", column="", expression=""):
    """Identity includes location, so two identically labelled actions remain distinct."""
    material = _json([SOURCE_REVISION, row_kind, source_path, str(line), str(column), expression])
    return "MX-" + hashlib.sha256(material.encode()).hexdigest()[:24]


def provisional_domain(source_path):
    """A filing aid, not a reviewed financial-domain or scope decision."""
    path = source_path.lower()
    if any(value in path for value in ("bulk-import", "bulkimport", "migration")):
        return "D15"
    if "teller" in path or "cashier" in path:
        return "D11"
    if any(value in path for value in ("provisioning", "/accounting", "journal", "gl-account")):
        return "D12"
    if any(value in path for value in ("datatable", "survey", "questionnaire", "document", "identifier")):
        return "D14"
    if any(value in path for value in ("/audits", "maker-checker", "makerchecker", "permission", "/roles")):
        return "D16"
    if "collection" in path:
        return "D10"
    if any(value in path for value in ("standing-instruction", "standinginstructions", "account-transfer", "/charges")):
        return "D09"
    if "report" in path:
        return "D13"
    if "fixed-deposit" in path or "recurring-deposit" in path:
        return "D07"
    if "share" in path:
        return "D08"
    if any(value in path for value in ("guarantor", "collateral", "reschedul", "refinanc", "re-age", "reage", "working-capital")):
        return "D05"
    if "saving" in path:
        return "D06"
    if "loan" in path or "floating-rate" in path:
        return "D04"
    if "/clients/" in path:
        return "D02"
    if "/groups/" in path or "/centers/" in path:
        return "D03"
    if "/tasks/" in path or "notification" in path:
        return "D17"
    if "/organization/" in path or "/system/" in path or "/zitadel/" in path:
        return "D01"
    if "/core/http/" in path or "interceptor" in path:
        return "D18"
    return "D19"


def _location(text, offset):
    return text.count("\n", 0, offset) + 1, offset - text.rfind("\n", 0, offset)


def _row(kind, path, line="", column="", expression="", **values):
    parts = PurePosixPath(path).parts
    label = PurePosixPath(path).name.removesuffix(".component.ts").removesuffix(".component.html")
    label = label.replace("-", " ")
    row = dict.fromkeys(FIELDNAMES, "")
    row.update(id=stable_id(kind, path, line, column, expression), row_kind=kind,
        domain=provisional_domain(path), subdomain="/".join(parts[2:4]), persona="UNREVIEWED",
        operator_goal=f"Review {label}: {kind.replace('_', ' ')} (heuristic; owner scope review required).",
        mifos_menu_screen_action=label, source_repository=SOURCE_REPOSITORY, source_revision=SOURCE_REVISION,
        source_path=path, source_line=str(line), source_column=str(column),
        source_url=SOURCE_ROOT + path + (f"#L{line}" if line else ""), source_expression=expression,
        scope_review="OWNER_SCOPE_REVIEW_REQUIRED: domain, persona and goal are provisional; no scope approval inferred.",
        extraction_evidence="PINNED_SOURCE_FACT_ONLY", status="NOT_MAPPED",
        blocker="Semantic workflow mapping, source conditions, native implementation, security and acceptance evidence are unreviewed.",
        resolution_waiver_owner="UNASSIGNED",
        acceptance_criteria="Owner approves scope and operator goal; review complete source dependencies, exact remote contract, native CE/EE flow, negative security tests, independent review and authenticated synthetic UAT.")
    unknown = values.keys() - row.keys()
    if unknown:
        raise ValueError(f"Unknown matrix fields: {', '.join(sorted(unknown))}.")
    row.update(values)
    return row


def curated_obligation(identifier, domain, operator_goal, **values):
    """Create a separately reviewed domain/ERP obligation without source invention."""
    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", identifier):
        raise ValueError("Curated obligations need a stable explicit identifier.")
    defaults = {"id": "CURATED-" + identifier, "domain": domain, "operator_goal": operator_goal,
        "source_url": "", "extraction_evidence": "CURATED_OBLIGATION"}
    defaults.update(values)
    return _row("curated_obligation", "", **defaults)


def _tree_evidence(tree):
    """Verify canonical Git identity; label historical app listings conservatively."""
    canonical = any(key in tree for key in ("repository", "revision", "commit_tree_sha"))
    if canonical:
        entries = _source_helper.validate_tree(tree, SOURCE_REVISION)
        blobs = sum(item["type"] == "blob" for item in entries.values())
        return {"tree_input_kind": "CANONICAL_COMPLETE_REPOSITORY_TREE",
            "tree_scope": "Complete repository tree identity validated; source extraction remains src/app-only.",
            "input_tree_sha": tree["sha"], "root_tree_sha": tree["sha"], "root_tree_identity_verified": True,
            "repository_entries": len(entries), "repository_blobs": blobs,
            "provided_entries": len(entries), "provided_blobs": blobs}
    if tree.get("sha") != SOURCE_REVISION:
        raise ValueError("The legacy app listing does not match the pinned Mifos revision.")
    if tree.get("truncated") or not isinstance(tree.get("tree"), list):
        raise ValueError("A truncated or invalid source listing cannot establish the inventory scope.")
    return {"tree_input_kind": "LEGACY_APP_BLOB_LIST_UNVERIFIED_ROOT",
        "tree_scope": "Legacy app listing; repository root-tree identity and complete repository scope are unverified.",
        "input_tree_sha": tree["sha"], "root_tree_sha": "", "root_tree_identity_verified": False,
        "repository_entries": None, "repository_blobs": None,
        "provided_entries": len(tree["tree"]),
        "provided_blobs": sum(item.get("type") == "blob" for item in tree["tree"])}


def _verified_sources(source_root, tree, strict=True):
    tree_evidence = _tree_evidence(tree)
    source_root = Path(source_root).resolve()
    repository_layout = (source_root / "src/app").is_dir()
    expected = {}
    for item in tree.get("tree", []):
        path = item.get("path", "")
        if item.get("type") != "blob" or not path.startswith("src/app/") or not path.endswith(SOURCE_SUFFIXES):
            continue
        if "\\" in path or ":" in path or any(part in {"", ".", ".."} for part in path.split("/")) or item.get("mode") == "120000":
            raise ValueError("Invalid source-tree path or symbolic link.")
        if path in expected or not re.fullmatch(r"[a-f0-9]{40}", item.get("sha", "")):
            raise ValueError("Duplicate source path or invalid source blob hash.")
        expected[path] = item["sha"]
    if not expected:
        raise ValueError("No pinned app source files were provided.")
    sources, missing = {}, []
    for path, expected_hash in sorted(expected.items()):
        target = (source_root / (path if repository_layout else path.removeprefix("src/app/"))).resolve()
        if not target.is_relative_to(source_root):
            raise ValueError("Source path escaped the pinned source cache.")
        if not target.is_file():
            missing.append(path)
            continue
        data = target.read_bytes()
        digest = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if digest != expected_hash:
            raise ValueError(f"Source blob does not match the pinned tree: {path}.")
        sources[path] = data.decode("utf-8")
    if missing and strict:
        raise ValueError(f"Pinned source files are missing ({len(missing)}); first: {missing[0]}.")
    manifest = {"source_repository": SOURCE_REPOSITORY, "source_revision": SOURCE_REVISION,
        "extractor_version": EXTRACTOR_VERSION, **tree_evidence,
        "extraction_scope": "src/app TS/HTML/JSON/SCSS only; external assets and runtime source are not extracted.",
        "app_only_extraction": True,
        "repository_blobs_outside_extraction_scope": (
            tree_evidence["repository_blobs"] - len(expected) if tree_evidence["root_tree_identity_verified"] else None),
        "expected_files": len(expected), "verified_files": len(sources), "missing_files": missing,
        "expected_ts_html_files": sum(path.endswith((".ts", ".html")) for path in expected),
        "verified_ts_html_files": sum(path.endswith((".ts", ".html")) for path in sources),
        "verified_by_extension": dict(sorted(Counter(PurePosixPath(path).suffix for path in sources).items())),
        "expected_components": sum(path.endswith(".component.ts") for path in expected),
        "verified_components": sum(path.endswith(".component.ts") for path in sources),
        "excluded_source_specs": sorted(path for path in sources if path.endswith(".spec.ts")),
        "extension_scope": list(SOURCE_SUFFIXES),
        "excluded_app_files": sorted(item["path"] for item in tree.get("tree", [])
            if item.get("type") == "blob" and item.get("path", "").startswith("src/app/")
            and not item["path"].endswith(SOURCE_SUFFIXES)),
        "outside_extraction_scope_gaps": ["src/environments", "src/assets", "repository runtime/build configuration"]}
    return sources, manifest


def source_manifest(source_root, tree, strict=True):
    """Return local Git-blob verification evidence, without network access."""
    return _verified_sources(source_root, tree, strict)[1]


def _tokens(text):
    """Small source lexer: ignore comments, preserve literal strings and offsets."""
    result, index = [], 0
    while index < len(text):
        character = text[index]
        if character.isspace():
            index += 1
        elif text.startswith("//", index):
            newline = text.find("\n", index + 2)
            index = len(text) if newline < 0 else newline
        elif text.startswith("/*", index):
            end = text.find("*/", index + 2)
            index = len(text) if end < 0 else end + 2
        elif character in "'\"`":
            start, quote = index, character
            index += 1
            while index < len(text):
                if text[index] == "\\":
                    index += 2
                elif text[index] == quote:
                    index += 1
                    break
                else:
                    index += 1
            result.append(Token("string", text[start + 1:index - 1], start, index, quote))
        elif character.isalpha() or character in "_$":
            start = index
            index += 1
            while index < len(text) and (text[index].isalnum() or text[index] in "_$"):
                index += 1
            result.append(Token("identifier", text[start:index], start, index))
        else:
            result.append(Token("punctuation", character, index, index + 1))
            index += 1
    return result


def _decoded_template(token):
    """Decode common TS string escapes while retaining original source positions."""
    result, offsets, index = [], [], 0
    escapes = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f", "v": "\v"}
    while index < len(token.value):
        start = index
        character = token.value[index]
        if character == "\\" and index + 1 < len(token.value):
            index += 1
            character = token.value[index]
            if character == "\n":
                index += 1
                continue
            character = escapes.get(character, character)
        result.append(character)
        offsets.append(token.start + 1 + start)
        index += 1
    return "".join(result), offsets


class _TemplateFacts(HTMLParser):
    def __init__(self, template, source, path, parent_id, offsets=None):
        super().__init__(convert_charrefs=False)
        self.template, self.source, self.path, self.parent_id = template, source, path, parent_id
        self.offsets = offsets
        self.line_starts = [0] + [match.end() for match in re.finditer("\n", template)]
        self.rows = []

    def handle_starttag(self, tag, attrs):
        del attrs
        raw = self.get_starttag_text()
        start = self.line_starts[self.getpos()[0] - 1] + self.getpos()[1]
        tag_end = re.match(r"<\s*[^\s/>]+", raw).end()
        attributes = []
        for match in _ATTRIBUTES.finditer(raw, tag_end):
            name = match.group(1)
            value = next((part for part in match.groups()[1:] if part is not None), "")
            attributes.append((name, html.unescape(value), start + match.start()))
        conditions = {name: value for name, value, _ in attributes
            if any(part in name.lower() for part in ("permission", "ngif", "disabled"))}
        for name, value, offset in attributes:
            lower = name.lower()
            if name.startswith("(") and name.endswith(")") or lower.startswith("on-"):
                kind = "template_action"
            elif lower in {"routerlink", "[routerlink]", "href", "[href]"}:
                kind = "navigation"
            elif lower in {"mat-dialog-close", "[mat-dialog-close]"}:
                kind = "dialog_action_review"
            elif lower.startswith("[(") and lower.endswith(")]"):
                kind = "model_binding_review"
            else:
                continue
            source_offset = self.offsets[offset] if self.offsets else offset
            line, column = _location(self.source, source_offset)
            self.rows.append(_row(kind, self.path, line, column, f"{name}={value}", parent_ids=self.parent_id,
                mifos_menu_screen_action=f"{tag} {name}", source_conditionals=_json(conditions) if conditions else "",
                upstream_source_gaps="Template syntax is extraction evidence only; resolve control-flow, permission flags, dialog result and handler dependencies manually."))


def extract_template(template, source_path, parent_id="", *, source_text=None, offsets=None):
    """Expose template facts for tests/curation; never map events to HTTP by guesswork."""
    parser = _TemplateFacts(template, source_text if source_text is not None else template, source_path, parent_id, offsets)
    parser.feed(template)
    parser.close()
    return parser.rows


def _http_facts(text, tokens):
    calls = []
    for index, token in enumerate(tokens):
        if token.kind != "identifier" or token.value not in {"http", "httpClient"}:
            continue
        if index + 3 >= len(tokens) or tokens[index + 1].value != "." or tokens[index + 2].value not in _HTTP_METHODS:
            continue
        cursor = index + 3
        if tokens[cursor].value == "<":
            nesting = 1
            cursor += 1
            while cursor < len(tokens) and nesting:
                nesting += (tokens[cursor].value == "<") - (tokens[cursor].value == ">")
                cursor += 1
        if cursor + 1 >= len(tokens) or tokens[cursor].value != "(":
            continue
        first = tokens[cursor + 1]
        end = cursor + 1
        nesting = 0
        while end < len(tokens):
            value = tokens[end].value
            if tokens[end].kind != "string":
                if not nesting and value in {",", ")"}:
                    break
                nesting += value in {"(", "[", "{"}
                nesting -= value in {")", "]", "}"}
            end += 1
        line, column = _location(text, token.start)
        literal = first.kind == "string"
        # Literal-plus-expression URLs are not complete literal endpoints.
        complete = literal and end == cursor + 2
        expression = text[first.start:tokens[end - 1].end] if end > cursor + 1 else ""
        calls.append({"method": tokens[index + 2].value.upper(), "path": first.value if complete else "",
            "line": line, "column": column, "expression": first.value if complete else expression,
            "literal": complete})
    return calls


def _route_pattern(path):
    path = path.split("?", 1)[0].strip("/")
    path = re.sub(r"^v1/", "", path)
    return re.sub(r"\{[^}]*\}", "{}", re.sub(r"\$\{[^}]*\}", "{}", path))


def _candidate_summary(keys, catalog):
    entries = {entry["key"]: entry for entry in catalog.get("capabilities", [])}
    summaries = []
    for key in sorted(set(keys)):
        if key not in entries:
            summaries.append({"key": key, "issue": "Inventory candidate is absent from current catalog."})
            continue
        entry = entries[key]
        body = entry.get("body") or {}
        seen = set()
        while "$ref" in body:
            name = body["$ref"].rsplit("/", 1)[-1]
            if name in seen or name not in catalog.get("schemas", {}):
                break
            seen.add(name)
            body = catalog["schemas"][name]
        summaries.append({"key": key, "blocked": entry.get("blocked", ""),
            "fields": sorted(body.get("properties", {})), "required": body.get("required", []),
            "conditionals": {name: value for name, value in body.items() if name.startswith("x-mfierp-")},
            "admin_only_candidate": bool(entry.get("admin_only"))})
    return _json(summaries)


def _http_row(path, fact, catalog, existing=None):
    existing = existing or {}
    keys = list(existing.get("capabilities", []))
    if not keys and fact["literal"]:
        keys = [entry["key"] for entry in catalog.get("capabilities", [])
            if entry.get("method") == fact["method"] and _route_pattern(entry["path"]) == _route_pattern(fact["path"])]
    query = fact["path"].split("?", 1)[1] if "?" in fact["path"] else ""
    command = next((part.split("=", 1)[1] for part in query.split("&") if part.startswith("command=")), "")
    return _row("http_contract" if fact["literal"] else "computed_http_review", path, fact["line"], fact["column"],
        f"{fact['method']} {fact['expression']}", fineract_endpoint=fact["path"], http_method=fact["method"],
        fineract_command=command, contract_candidate_keys=_json(sorted(set(keys))),
        contract_candidate_status=existing.get("status", "UNREVIEWED_SOURCE_CALL"),
        schema_fields_conditionals=_candidate_summary(keys, catalog) if keys else "",
        upstream_source_gaps="Contract obligation only. Literal URL is preserved as written, not a verified deployed endpoint. Resolve API-prefix/version interception, query/HttpParams, command variants, payload transformations and callers separately.",
        blocker="A catalog candidate never establishes an exact source command, native workflow, authorization, implementation or UAT. Semantic and contract review required.")


def _source_review_rows(path, text, tokens):
    rows = []
    if not path.endswith(".component.ts"):
        rows.append(_row("source_review_obligation", path, 1, 1,
            upstream_source_gaps="Review this module's callers, control-flow, route/config tables, permission/feature flags, payload transformations and error/recovery behavior; file presence is not feature mapping."))
    routing = "routing" in PurePosixPath(path).name
    for index, token in enumerate(tokens):
        if routing and token.value == "path" and index + 2 < len(tokens) and tokens[index + 1].value == ":" and tokens[index + 2].kind == "string":
            line, column = _location(text, token.start)
            rows.append(_row("route_review", path, line, column, tokens[index + 2].value,
                upstream_source_gaps="Resolve full parent/child route, guards, resolver dependencies, redirects and actual navigation; this fragment is not a reviewed menu."))
        if token.kind == "identifier" and token.value in {"case", "default"}:
            cursor = index + 1
            while cursor < min(len(tokens), index + 30) and tokens[cursor].value != ":":
                cursor += 1
            if cursor < len(tokens) and tokens[cursor].value == ":":
                line, column = _location(text, token.start)
                expression = text[token.start:tokens[cursor].end]
                rows.append(_row("switch_branch_review", path, line, column, expression,
                    upstream_source_gaps="A source branch may select distinct financial workflows, errors or dependencies. Review its full body and caller conditions; do not merge branches into one completed action."))
        signal = ""
        if token.value in {"Output", "HostListener"} and index and tokens[index - 1].value == "@":
            signal = "decorator " + token.value
        elif token.value in {"EventEmitter", "FileReader"} and index and tokens[index - 1].value == "new":
            signal = "new " + token.value
        elif token.value in {"saveAs", "print"} and index + 1 < len(tokens) and tokens[index + 1].value == "(":
            signal = token.value + "()"
        elif token.value == "close" and index > 1 and tokens[index - 1].value == "." and re.search(r"dialog|ref", tokens[index - 2].value, re.IGNORECASE):
            signal = tokens[index - 2].value + ".close()"
        if signal:
            line, column = _location(text, token.start)
            rows.append(_row("interaction_review", path, line, column, signal,
                upstream_source_gaps="Review dialog/output/host event, export/print or file handling behavior and its privacy/cancel/error paths; no operator workflow inferred from this token."))
    return rows


def _gap_rows():
    facts = [
        ("outside-environments", "D18", "src/environments", "Environment/runtime API prefixes, feature flags, identity/RBAC settings and deployed variant are outside this generator's app-only extraction scope."),
        ("outside-assets-i18n", "D19", "src/assets", "Assets, translation catalogs and locale-driven labels/menu variants are outside this generator's app-only extraction scope."),
        ("outside-build-runtime", "D20", "repository-root", "Repository build/dependency/runtime configuration and non-app source are outside this generator's app-only extraction scope; review their indexed repository paths separately."),
        ("dynamic-permissions-menus", "D16", "src/app", "Review permission directives, guards, feature flags and dynamic menu/action tables together. Template visibility does not establish server authorization or approved scope."),
        ("workflow-dependencies", "D18", "src/app", "Resolve component-to-service, routing/resolver joins, action maps, computed resources, branches, default/catchError and remote side effects. Extracted events and literal calls do not establish workflow completeness."),
        ("template-control-flow", "D19", "src/app", "Review Angular structural/block control-flow, shared dialogs, nested content, translated labels and responsive/cancel/error states. Static extraction is not rendered browser evidence."),
        ("owner-inventory-approval", "D19", "src/app", "Owner must approve the complete operator goal/persona/domain inventory, contextual dependencies, edition/ERP obligations and explicit exclusions before parity denominators are defined."),
    ]
    return [_row("inventory_gap", path, expression=identifier, domain=domain,
        source_url="", extraction_evidence="UNREVIEWED_SCOPE_OBLIGATION", upstream_source_gaps=gap, blocker=gap)
        for identifier, domain, path, gap in facts]


def _deduplicate(rows):
    result = {}
    for row in rows:
        if row["id"] not in result:
            result[row["id"]] = row
        else:
            # Shared external templates are one source action with several screen contexts.
            parents = set(filter(None, result[row["id"]]["parent_ids"].split(";")))
            parents.update(filter(None, row["parent_ids"].split(";")))
            result[row["id"]]["parent_ids"] = ";".join(sorted(parents))
    return sorted(result.values(), key=lambda row: (row["source_path"], int(row["source_line"] or 0),
        int(row["source_column"] or 0), row["row_kind"], row["id"]))


def build_matrix(source_root, tree, endpoint_inventory, catalog, curated_rows=(), *, strict=True):
    """Build extraction-only rows. Inputs are loaded objects; this function never fetches."""
    if endpoint_inventory.get("source_revision") != SOURCE_REVISION or endpoint_inventory.get("source_repository") != SOURCE_REPOSITORY:
        raise ValueError("Endpoint inventory is not pinned to the reviewed Mifos source.")
    sources, manifest = _verified_sources(source_root, tree, strict)
    existing = {}
    for call in endpoint_inventory.get("calls", []):
        key = (call["source"], call["line"], call["method"], call["path"])
        if key in existing and existing[key] != call:
            raise ValueError("Conflicting endpoint inventory entries.")
        existing[key] = call
    rows, matched, template_contexts = [], set(), {}
    for path, text in sorted(sources.items()):
        if not path.endswith(".ts") or path.endswith(".spec.ts"):
            continue
        tokens = _tokens(text)
        parent = ""
        if path.endswith(".component.ts"):
            offset = next((token.start for index, token in enumerate(tokens)
                if token.value == "Component" and index and tokens[index - 1].value == "@"), 0)
            line, column = _location(text, offset)
            screen = _row("screen", path, line, column,
                upstream_source_gaps="Component declaration is a source screen/container fact, not reviewed menu reachability or a complete operator task.")
            rows.append(screen)
            parent = screen["id"]
            for index, token in enumerate(tokens[:-2]):
                if token.value not in {"templateUrl", "template"} or tokens[index + 1].value != ":" or tokens[index + 2].kind != "string":
                    continue
                literal = tokens[index + 2]
                if token.value == "templateUrl":
                    template_path = posixpath.normpath(posixpath.join(posixpath.dirname(path), literal.value))
                    if template_path in sources and template_path.startswith("src/app/"):
                        template_contexts.setdefault(template_path, []).append(parent)
                    else:
                        missing_line, missing_column = _location(text, literal.start)
                        rows.append(_row("inventory_gap", path, missing_line, missing_column, literal.value,
                            parent_ids=parent, blocker="Referenced template is not available in the verified source set."))
                else:
                    template, offsets = _decoded_template(literal)
                    template_line, template_column = _location(text, literal.start)
                    rows.append(_row("template", path, template_line, template_column, "inline template",
                        parent_ids=parent, upstream_source_gaps="Inline template fact only; review rendered states and operator context."))
                    rows.extend(extract_template(template, path, parent, source_text=text, offsets=offsets))
        rows.extend(_source_review_rows(path, text, tokens))
        for fact in _http_facts(text, tokens):
            key = (path, fact["line"], fact["method"], fact["path"])
            rows.append(_http_row(path, fact, catalog, existing.get(key)))
            if key in existing:
                matched.add(key)
    for path, text in sorted(sources.items()):
        if path.endswith(".html"):
            parents = ";".join(sorted(set(template_contexts.get(path, []))))
            rows.append(_row("template", path, 1, 1, parent_ids=parents,
                upstream_source_gaps="Template fact only; review rendered states, labels and contextual dependencies."))
            rows.extend(extract_template(text, path, parents))
            if not parents:
                rows.append(_row("template_context_review", path, 1, 1,
                    upstream_source_gaps="No static templateUrl owner was found; establish rendered/shared template context before workflow mapping."))
        elif path.endswith((".json", ".scss")):
            rows.append(_row("source_review_obligation", path, 1, 1,
                expression="metadata" if path.endswith(".json") else "style",
                upstream_source_gaps="Review metadata/configuration or style-driven visibility, layout, accessibility and responsive variants; file verification is not operator acceptance."))
    for key, call in sorted(existing.items()):
        if key in matched:
            continue
        fact = {"method": call["method"], "path": call["path"], "line": call["line"], "column": "",
            "expression": call["path"], "literal": True}
        row = _http_row(call["source"], fact, catalog, call)
        row["extraction_evidence"] = "PRIOR_ENDPOINT_INVENTORY_REQUIRES_LEXICAL_RECONCILIATION"
        row["blocker"] = "Prior inventory call was not reproduced by the conservative source lexer; verify source line, HTTP alias, expression and endpoint before semantic mapping."
        if call["source"] not in sources:
            row["extraction_evidence"] = "PRIOR_ENDPOINT_INVENTORY_OUTSIDE_VERIFIED_SOURCE"
            row["blocker"] = "Prior inventory references source outside the verified source set; obtain and verify that source before semantic mapping."
        rows.append(row)
    rows.extend(_gap_rows())
    for path in manifest["missing_files"]:
        rows.append(_row("inventory_gap", path, extraction_evidence="SOURCE_MISSING",
            source_url="", blocker="Pinned app source is missing. Extraction is explicitly incomplete."))
    for path in manifest["excluded_app_files"]:
        rows.append(_row("inventory_gap", path, extraction_evidence="SOURCE_EXTENSION_OUTSIDE_EXTRACTION_SCOPE",
            source_url="", blocker="This app file is outside the verified extension scope; inspect its relevance separately."))
    return append_curated_rows(_deduplicate(rows), curated_rows)


def _has_evidence(value):
    return bool(value and value.strip() and not re.match(
        r"^(?:UNREVIEWED|UNKNOWN|UNASSIGNED|PENDING|NOT(?:[ _]|$)|N/A|TODO|TBD)", value.strip(), re.IGNORECASE)
        and not re.search(r"(?:^|[ _])(?:NOT[ _](?:TESTED|VERIFIED|IMPLEMENTED|AVAILABLE|RUN)|UNVERIFIED|UNTESTED)(?:$|[ _;:])",
            value, re.IGNORECASE))


def validate_rows(rows):
    """Machine-check evidence fields; this cannot authenticate reviewer/UAT claims."""
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(FIELDNAMES):
            raise ValueError("Matrix rows need exactly the declared columns.")
        if not all(isinstance(value, str) for value in row.values()):
            raise ValueError("Matrix cells must be explicit text.")
        if not row["id"] or row["id"] in seen:
            raise ValueError("Matrix rows need unique stable IDs.")
        seen.add(row["id"])
        if row["status"] not in STATUS_DEFINITIONS:
            raise ValueError("Unknown functional-matrix status.")
        curated = row["extraction_evidence"].startswith("CURATED_")
        if not curated and (row["source_repository"] != SOURCE_REPOSITORY or row["source_revision"] != SOURCE_REVISION):
            raise ValueError("Matrix source metadata must retain the pinned repository and revision.")
        if curated and (not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", row["source_repository"])
                or not re.fullmatch(r"[a-f0-9]{40}", row["source_revision"])):
            raise ValueError("Curated provenance needs an explicit repository and exact revision.")
        if not re.fullmatch(r"D(?:0[1-9]|1[0-9]|20)", row["domain"]):
            raise ValueError("Matrix rows need a declared D01-D20 domain (provisional until reviewed).")
        for field in ("source_line", "source_column"):
            if row[field] and not re.fullmatch(r"[1-9][0-9]*", row[field]):
                raise ValueError("Source locations must be positive integers or explicitly blank.")
        if row["source_url"]:
            source_root = f"https://github.com/{row['source_repository']}/blob/{row['source_revision']}/"
            expected_url = source_root + row["source_path"] + (f"#L{row['source_line']}" if row["source_line"] else "")
            if row["source_url"] != expected_url:
                raise ValueError("Source evidence links must match the pinned path and line.")
        missing = [field for field in _STATUS_GATES.get(row["status"], ()) if not _has_evidence(row[field])]
        if missing:
            raise ValueError(f"{row['id']}: {row['status']} requires evidence: {', '.join(missing)}.")
        if row["accepted_at"]:
            try:
                datetime.fromisoformat(row["accepted_at"].replace("Z", "+00:00"))
            except ValueError as error:
                raise ValueError("Acceptance timestamps must use an ISO 8601 date or datetime.") from error
    return rows


def append_curated_rows(rows, curated_rows):
    result = [dict(row) for row in rows] + [dict(row) for row in curated_rows]
    validate_rows(result)
    return sorted(result, key=lambda row: (row["source_path"], int(row["source_line"] or 0),
        int(row["source_column"] or 0), row["row_kind"], row["id"]))


def apply_evidence(rows, evidence):
    """Apply explicit row-ID keyed review evidence; never promote from code/catalog counts."""
    validate_rows(rows)
    result = {row["id"]: dict(row) for row in rows}
    for row_id, changes in evidence.items():
        if row_id not in result or changes.keys() & _SOURCE_FACT_FIELDS or changes.keys() - set(FIELDNAMES):
            raise ValueError("Evidence must reference an existing stable row and must preserve extracted source facts.")
        result[row_id].update(changes)
    return append_curated_rows([], result.values())


def matrix_summary(rows):
    validate_rows(rows)
    return {"extractor_version": EXTRACTOR_VERSION, "source_revision": SOURCE_REVISION, "rows": len(rows),
        "by_row_kind": dict(sorted(Counter(row["row_kind"] for row in rows).items())),
        "by_provisional_domain": dict(sorted(Counter(row["domain"] for row in rows).items())),
        "by_status": dict(sorted(Counter(row["status"] for row in rows).items())),
        "status_definitions": STATUS_DEFINITIONS,
        "limitations": ["Source extraction is not owner-approved workflow inventory or operator acceptance.",
            "Extraction is src/app-only even with a complete repository tree input; environments, assets/i18n and repository build/runtime need separate review.",
            "HTTP aliases, computed routes, template control-flow and cross-file dependencies require semantic review.",
            "Catalog matches are contract candidates only; native implementation, edition, browser and UAT evidence are independent."]}


def summarize(rows):
    """Public summary API; retained matrix_summary name supports existing callers."""
    return matrix_summary(rows)


def write_matrix(rows, output_path):
    validate_rows(rows)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(append_curated_rows([], rows))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--tree", type=Path, default=Path(".research/mifos-repository-tree.json"))
    parser.add_argument("--endpoints", type=Path, default=Path("docs/parity/mifos-endpoints.json"))
    parser.add_argument("--catalog", type=Path, default=Path("addons/mfierp/services/catalog.json"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--curated", type=Path, help="Optional explicit full-column curated obligation rows (JSON list).")
    parser.add_argument("--evidence", type=Path, help="Optional explicit row-ID keyed evidence updates (JSON object).")
    parser.add_argument("--allow-missing", action="store_true", help="Emit missing-source obligations instead of silently claiming a complete extraction.")
    args = parser.parse_args()
    read = lambda path: json.loads(path.read_text(encoding="utf-8"))
    tree, endpoints, catalog = read(args.tree), read(args.endpoints), read(args.catalog)
    rows = build_matrix(args.source_root, tree, endpoints, catalog,
        read(args.curated) if args.curated else (), strict=not args.allow_missing)
    if args.evidence:
        rows = apply_evidence(rows, read(args.evidence))
    if args.output:
        write_matrix(rows, args.output)
    summary = {**matrix_summary(rows), "source_manifest": source_manifest(args.source_root, tree, not args.allow_missing)}
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
