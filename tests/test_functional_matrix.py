"""Pinned-source extraction and evidence-gate regressions, without Odoo or network."""
import copy
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


module = importlib.util.spec_from_file_location(
    "functional_matrix", Path(__file__).resolve().parents[1] / "scripts/build_functional_matrix.py")
matrix = importlib.util.module_from_spec(module)
module.loader.exec_module(matrix)


class FunctionalMatrixTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.files = {
            "src/app/clients/client.component.ts": (
                "import { Component } from '@angular/core';\n"
                "\n@Component({\n  templateUrl: './shared.component.html'\n})\nexport class Client {}\n"),
            "src/app/clients/other.component.ts": (
                "@Component({ templateUrl: './shared.component.html' })\nexport class Other {}\n"),
            "src/app/clients/shared.component.html": (
                '<button\n  (click)="submit(\'quoted > value\')"\n'
                '  [disabled]="busy" *ngIf="canWrite">Send</button>\n'
                '<button (click)="submit(\'quoted > value\')">Again</button>\n'
                '<a [routerLink]="[\'/clients\', client.id]">Client</a>\n'
                '<button mat-dialog-close>Cancel</button>\n'
                '<input [(ngModel)]="name" />\n'),
            "src/app/clients/clients.service.ts": (
                "// this.http.post('/ignored-comment', body);\n"
                "const example = \"this.http.delete('/ignored-string')\";\n"
                "this.http.get<Client[]>('/clients');\n"
                "this.http.post(`/clients/${clientId}?command=activate`, body);\n"
                "this.http.get(prefix + '/clients/' + clientId);\n"
                "this.http.get(makePath('clients', clientId), {params});\n"
                "switch (command) {case 'reverse': undo(); break; default: fail();}\n"),
            "src/app/clients/clients-routing.module.ts": (
                "const routes = [{path: ':id', component: Client, resolve: {client: Resolver}, "
                "canActivate: [Guard]}];\n"),
            "src/app/clients/client.resolver.ts": "export class Resolver { resolve() { return service.load(); } }\n",
            "src/app/core/auth.guard.ts": "export class Guard { canActivate() { return auth.allowed; } }\n",
            "src/app/clients/client.component.scss": ".mobile { display: none; }\n",
            "src/app/clients/menu.json": '{"label":"Clients","permission":"READ_CLIENT"}\n',
            "src/app/clients/client.component.spec.ts": "describe('client', () => {});\n",
            "src/app/clients/README.md": "Additional app guidance outside the extension scope.\n",
        }
        self.tree = {"sha": matrix.SOURCE_REVISION, "tree": []}
        for path, text in self.files.items():
            data = text.encode("utf-8")
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            self.tree["tree"].append({"path": path, "type": "blob", "mode": "100644",
                "sha": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()})
        self.inventory = {"source_repository": matrix.SOURCE_REPOSITORY,
            "source_revision": matrix.SOURCE_REVISION, "calls": [{
                "source": "src/app/clients/clients.service.ts", "line": 3,
                "method": "GET", "path": "/clients", "status": "TYPED_CONTRACT_CANDIDATE",
                "capabilities": ["get_clients"], "operator_workflow_verified": True, "live_uat_verified": True}]}
        self.catalog = {"capabilities": [{"key": "get_clients", "method": "GET", "path": "/v1/clients",
            "blocked": "", "body": {"properties": {"officeId": {"type": "integer"}}}, "admin_only": True}]}

    def build(self, **kwargs):
        return matrix.build_matrix(self.root, self.tree, self.inventory, self.catalog, **kwargs)

    def canonical_tree(self):
        """Build a complete synthetic Git tree; outside-app blobs need no cache file."""
        entries = {item["path"]: dict(item, size=len(self.files[item["path"]].encode("utf-8")))
            for item in self.tree["tree"]}
        outside = b'{"outside":"not extracted"}'
        path = "src/assets/translations/en.json"
        entries[path] = {"path": path, "type": "blob", "mode": "100644", "size": len(outside),
            "sha": matrix._source_helper.git_hash("blob", outside)}
        for path in list(entries):
            parent = Path(path).parent.as_posix()
            while parent != ".":
                entries.setdefault(parent, {"path": parent, "type": "tree", "mode": "040000"})
                parent = Path(parent).parent.as_posix()
        for parent in sorted([path for path, item in entries.items() if item["type"] == "tree"] + [""],
                key=lambda path: (path.count("/"), len(path)), reverse=True):
            children = [item for path, item in entries.items()
                if (Path(path).parent.as_posix() if "/" in path else "") == parent]
            children.sort(key=lambda item: (Path(item["path"]).name
                + ("/" if item["type"] == "tree" else "")).encode())
            raw = b"".join(item["mode"].lstrip("0").encode() + b" " + Path(item["path"]).name.encode()
                + b"\0" + bytes.fromhex(item["sha"]) for item in children)
            digest = matrix._source_helper.git_hash("tree", raw)
            if parent:
                entries[parent]["sha"] = digest
            else:
                root_sha = digest
        return {"repository": matrix.SOURCE_REPOSITORY, "revision": matrix.SOURCE_REVISION,
            "sha": root_sha, "commit_tree_sha": root_sha, "truncated": False, "tree": list(entries.values())}

    def test_canonical_tree_adapter_preserves_app_ids_and_exposes_repository_identity(self):
        legacy_rows = self.build()
        legacy_manifest = matrix.source_manifest(self.root, self.tree)
        self.assertEqual(legacy_manifest["tree_input_kind"], "LEGACY_APP_BLOB_LIST_UNVERIFIED_ROOT")
        self.assertFalse(legacy_manifest["root_tree_identity_verified"])
        self.assertEqual(legacy_manifest["root_tree_sha"], "")
        self.assertIsNone(legacy_manifest["repository_blobs"])
        canonical = self.canonical_tree()
        with patch.object(matrix._source_helper, "PINNED_TREE_SHA", canonical["sha"]):
            rows = matrix.build_matrix(self.root, canonical, self.inventory, self.catalog)
            canonical["tree"].reverse()
            self.assertEqual(rows, matrix.build_matrix(self.root, canonical, self.inventory, self.catalog))
            manifest = matrix.source_manifest(self.root, canonical)
        self.assertEqual(rows, legacy_rows)
        self.assertEqual(manifest["tree_input_kind"], "CANONICAL_COMPLETE_REPOSITORY_TREE")
        self.assertTrue(manifest["root_tree_identity_verified"])
        self.assertEqual(manifest["root_tree_sha"], canonical["sha"])
        self.assertEqual(manifest["repository_entries"], len(canonical["tree"]))
        self.assertEqual(manifest["repository_blobs"], len(self.files) + 1)
        self.assertEqual(manifest["verified_files"], 10)
        self.assertEqual(manifest["repository_blobs_outside_extraction_scope"], 2)
        self.assertTrue(manifest["app_only_extraction"])
        self.assertFalse(any(row["source_path"] == "src/assets/translations/en.json" for row in rows))
        self.assertNotIn("supplied tree is src/app-only", " ".join(matrix.summarize(rows)["limitations"]))

    def test_canonical_tree_identity_mismatch_partial_and_tampered_tree_are_rejected(self):
        canonical = self.canonical_tree()
        with patch.object(matrix._source_helper, "PINNED_TREE_SHA", canonical["sha"]):
            for change in ("repository", "revision", "sha", "commit_tree_sha", "truncated", "partial", "blob"):
                with self.subTest(change=change):
                    invalid = copy.deepcopy(canonical)
                    if change == "repository":
                        invalid[change] = "other/source"
                    elif change in {"revision", "sha", "commit_tree_sha"}:
                        invalid[change] = "0" * 40
                    elif change == "truncated":
                        invalid[change] = True
                    elif change == "partial":
                        invalid["tree"].pop(0)
                    else:
                        invalid["tree"][0]["sha"] = "0" * 40
                    with self.assertRaises(ValueError):
                        matrix.build_matrix(self.root, invalid, self.inventory, self.catalog)

    def test_deterministic_ids_rows_and_csv_ignore_tree_input_order(self):
        first = self.build()
        self.tree["tree"].reverse()
        self.inventory["calls"].reverse()
        second = self.build()
        self.assertEqual(first, second)
        self.assertEqual(len(first), len({row["id"] for row in first}))
        for row in first:
            self.assertEqual(row["id"], matrix.stable_id(row["row_kind"], row["source_path"],
                row["source_line"], row["source_column"], row["source_expression"]))
        target = self.root / "matrix.csv"
        matrix.write_matrix(first, target)
        initial_bytes = target.read_bytes()
        matrix.write_matrix(list(reversed(second)), target)
        self.assertEqual(initial_bytes, target.read_bytes())
        parsed = list(csv.DictReader(io.StringIO(initial_bytes.decode())))
        self.assertEqual(first, parsed)
        self.assertEqual(tuple(parsed[0]), matrix.FIELDNAMES)

    def test_same_label_actions_on_different_lines_have_separate_identity(self):
        actions = [row for row in self.build() if row["row_kind"] == "template_action"]
        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[0]["source_expression"], actions[1]["source_expression"])
        self.assertNotEqual(actions[0]["id"], actions[1]["id"])
        self.assertEqual([row["source_line"] for row in actions], ["2", "4"])
        self.assertEqual(actions[0]["source_column"], "3")

    def test_same_label_actions_on_same_line_keep_columns(self):
        rows = matrix.extract_template('<a (click)="go()"></a><a (click)="go()"></a>', "src/app/example.html")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["source_line"], rows[1]["source_line"])
        self.assertNotEqual(rows[0]["source_column"], rows[1]["source_column"])
        self.assertNotEqual(rows[0]["id"], rows[1]["id"])

    def test_quoted_multiline_attributes_preserve_expressions_and_conditions(self):
        rows = matrix.extract_template(
            '<button\n (click)="save(\'a > b\',\n item)"\n *ngIf="allowed" [disabled]="busy">Go</button>'
            "<a routerLink='/clients'>List</a>", "src/app/example.html")
        action, navigation = rows
        self.assertEqual(action["source_expression"], "(click)=save('a > b',\n item)")
        self.assertEqual(json.loads(action["source_conditionals"]), {"*ngIf": "allowed", "[disabled]": "busy"})
        self.assertEqual(action["source_line"], "2")
        self.assertEqual(navigation["row_kind"], "navigation")

    def test_shared_template_is_deduplicated_with_both_screen_contexts(self):
        rows = self.build()
        screens = [row for row in rows if row["row_kind"] == "screen"]
        templates = [row for row in rows if row["row_kind"] == "template"]
        self.assertEqual(len(screens), 2)
        self.assertEqual(len(templates), 1)
        expected_parents = ";".join(sorted(row["id"] for row in screens))
        self.assertEqual(templates[0]["parent_ids"], expected_parents)
        actions = [row for row in rows if row["row_kind"] == "template_action"]
        self.assertTrue(all(row["parent_ids"] == expected_parents for row in actions))
        client = next(row for row in screens if row["source_path"].endswith("/client.component.ts"))
        self.assertEqual(client["source_line"], "3")

    def test_inline_templates_keep_original_ts_locations_after_escaped_newlines(self):
        text = '@Component({template: "<div>\\n<button (click)=\\"go()\\">Go</button></div>"})'
        tokens = matrix._tokens(text)
        literal = next(token for token in tokens if token.kind == "string")
        template, offsets = matrix._decoded_template(literal)
        rows = matrix.extract_template(template, "src/app/inline.component.ts", source_text=text, offsets=offsets)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_line"], "1")
        self.assertEqual(rows[0]["source_column"], str(text.index("(click)") + 1))
        self.assertEqual(rows[0]["source_expression"], "(click)=go()")

    def test_navigation_cancel_and_two_way_bindings_have_explicit_obligations(self):
        kinds = {row["row_kind"] for row in self.build()}
        self.assertTrue({"navigation", "dialog_action_review", "model_binding_review"}.issubset(kinds))

    def test_api_candidates_never_escalate_implementation_or_uat_status(self):
        rows = self.build()
        call = next(row for row in rows if row["http_method"] == "GET" and row["fineract_endpoint"] == "/clients")
        self.assertEqual(call["contract_candidate_status"], "TYPED_CONTRACT_CANDIDATE")
        self.assertEqual(json.loads(call["contract_candidate_keys"]), ["get_clients"])
        self.assertIn("officeId", call["schema_fields_conditionals"])
        self.assertEqual({row["status"] for row in rows}, {"NOT_MAPPED"})
        for field in ("implementation_evidence", "odoo_menu_model_form_flow", "live_uat_evidence_link",
                "authenticated_integration_test", "ce_test_evidence", "ee_test_evidence"):
            self.assertTrue(all(not row[field] for row in rows))

    def test_http_lexer_ignores_comments_and_strings_and_preserves_computed_url(self):
        rows = [row for row in self.build() if row["http_method"]]
        self.assertEqual(len(rows), 4)
        computed = [row for row in rows if row["row_kind"] == "computed_http_review"]
        self.assertEqual(len(computed), 2)
        self.assertEqual({row["source_expression"] for row in computed}, {
            "GET prefix + '/clients/' + clientId", "GET makePath('clients', clientId)"})
        command = next(row for row in rows if row["http_method"] == "POST")
        self.assertEqual(command["fineract_command"], "activate")

    def test_noncomponent_resolver_guard_route_and_metadata_style_obligations(self):
        rows = self.build()
        review_paths = {row["source_path"] for row in rows if row["row_kind"] == "source_review_obligation"}
        for path in ("src/app/clients/client.resolver.ts", "src/app/core/auth.guard.ts",
                "src/app/clients/menu.json", "src/app/clients/client.component.scss"):
            self.assertIn(path, review_paths)
        route = next(row for row in rows if row["row_kind"] == "route_review")
        self.assertEqual(route["source_expression"], ":id")
        self.assertEqual(len([row for row in rows if row["row_kind"] == "switch_branch_review"]), 2)

    def test_source_manifest_verifies_all_scoped_extensions_and_lists_exclusions(self):
        manifest = matrix.source_manifest(self.root, self.tree)
        self.assertEqual(manifest["expected_files"], 10)
        self.assertEqual(manifest["verified_files"], 10)
        self.assertEqual(manifest["expected_ts_html_files"], 8)
        self.assertEqual(manifest["verified_by_extension"], {".html": 1, ".json": 1, ".scss": 1, ".ts": 7})
        self.assertEqual(manifest["excluded_source_specs"], ["src/app/clients/client.component.spec.ts"])
        self.assertEqual(manifest["excluded_app_files"], ["src/app/clients/README.md"])
        gap = next(row for row in self.build() if row["source_path"].endswith("README.md"))
        self.assertEqual(gap["extraction_evidence"], "SOURCE_EXTENSION_OUTSIDE_EXTRACTION_SCOPE")
        self.assertFalse(gap["source_url"])

    def test_missing_source_fails_strictly_and_explicit_opt_out_emits_gap(self):
        (self.root / "src/app/core/auth.guard.ts").unlink()
        with self.assertRaisesRegex(ValueError, "missing"):
            self.build()
        rows = self.build(strict=False)
        gap = next(row for row in rows if row["extraction_evidence"] == "SOURCE_MISSING")
        self.assertEqual(gap["status"], "NOT_MAPPED")
        self.assertIn("incomplete", gap["blocker"])

    def test_tampered_ts_or_style_source_is_rejected_even_when_missing_allowed(self):
        for path in ("src/app/clients/clients.service.ts", "src/app/clients/client.component.scss"):
            with self.subTest(path=path):
                target = self.root / path
                original = target.read_bytes()
                target.write_bytes(original + b"tampered")
                with self.assertRaisesRegex(ValueError, "does not match"):
                    self.build(strict=False)
                target.write_bytes(original)

    def test_pin_truncation_duplicates_traversal_and_symlink_tree_entries_rejected(self):
        for change in ("pin", "truncated", "duplicate", "dot", "parent", "symlink"):
            with self.subTest(change=change):
                tree = copy.deepcopy(self.tree)
                if change == "pin":
                    tree["sha"] = "0" * 40
                elif change == "truncated":
                    tree["truncated"] = True
                elif change == "duplicate":
                    tree["tree"].append(dict(tree["tree"][0]))
                elif change == "symlink":
                    tree["tree"][0]["mode"] = "120000"
                else:
                    tree["tree"][0]["path"] = "src/app/" + ("./" if change == "dot" else "../") + "escape.ts"
                with self.assertRaises(ValueError):
                    matrix.build_matrix(self.root, tree, self.inventory, self.catalog)

    def test_outside_tree_scope_and_prior_inventory_obligations_are_explicit_and_unique(self):
        call = {"source": "src/outside.service.ts", "line": 10, "method": "GET", "path": "/outside"}
        self.inventory["calls"].extend([call, dict(call)])
        rows = self.build()
        outside = [row for row in rows if row["source_path"] == call["source"]]
        self.assertEqual(len(outside), 1)
        self.assertEqual(outside[0]["extraction_evidence"], "PRIOR_ENDPOINT_INVENTORY_OUTSIDE_VERIFIED_SOURCE")
        gaps = {row["source_expression"]: row for row in rows if row["row_kind"] == "inventory_gap"}
        self.assertTrue({"outside-environments", "outside-assets-i18n", "outside-build-runtime"}.issubset(gaps))
        self.assertTrue(all(not gaps[key]["source_url"] for key in gaps if key.startswith("outside-")))

    def test_endpoint_inventory_pin_mismatch_and_conflicting_entries_rejected(self):
        self.inventory["source_revision"] = "wrong"
        with self.assertRaisesRegex(ValueError, "not pinned"):
            self.build()
        self.inventory["source_revision"] = matrix.SOURCE_REVISION
        duplicate = dict(self.inventory["calls"][0], status="DIFFERENT")
        self.inventory["calls"].append(duplicate)
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            self.build()

    def test_every_promoted_curated_status_enforces_all_declared_evidence_gates(self):
        for status, fields in matrix._STATUS_GATES.items():
            with self.subTest(status=status):
                row = matrix.curated_obligation("gate-" + status, "D18", "Review an explicit owner obligation", status=status)
                for field in fields:
                    row[field] = "reviewed/evidence-reference"
                if "accepted_at" in fields:
                    row["accepted_at"] = "2026-11-20T12:00:00Z"
                matrix.validate_rows([row])
                for field in fields:
                    missing = dict(row, **{field: ""})
                    with self.assertRaisesRegex(ValueError, "requires evidence"):
                        matrix.validate_rows([missing])

    def test_higher_statuses_retain_contract_and_authorization_gates(self):
        for status in ("IMPLEMENTED", "LOCAL_TEST_PASS", "STAGING_UAT_PASS", "OPERATOR_ACCEPTED"):
            self.assertTrue(set(matrix._STATUS_GATES["CONTRACT_VERIFIED"]).issubset(matrix._STATUS_GATES[status]))
        self.assertTrue({"ce_test_evidence", "ee_test_evidence", "negative_security_tests"}.issubset(
            matrix._STATUS_GATES["OPERATOR_ACCEPTED"]))

    def test_unreviewed_placeholders_invalid_dates_and_statuses_cannot_pass_gates(self):
        row = matrix.curated_obligation("source-mapped", "D01", "Map source", status="SOURCE_MAPPED")
        for placeholder in ("UNREVIEWED", " PENDING reviewer", "NOT VERIFIED", "NOT_VERIFIED", "N/A", "TODO",
                "EE_NOT_TESTED", "FINANCIAL_UAT_NOT_VERIFIED"):
            with self.subTest(placeholder=placeholder):
                row["semantic_mapping_evidence"] = placeholder
                with self.assertRaises(ValueError):
                    matrix.validate_rows([row])
        row["status"] = "DONE"
        with self.assertRaisesRegex(ValueError, "Unknown"):
            matrix.validate_rows([row])
        row["status"] = "NOT_MAPPED"
        row["accepted_at"] = "whenever"
        with self.assertRaisesRegex(ValueError, "ISO 8601"):
            matrix.validate_rows([row])

    def test_curated_ids_must_be_unique_and_source_facts_cannot_be_rewritten_as_evidence(self):
        rows = self.build()
        row = rows[0]
        with self.assertRaisesRegex(ValueError, "unique"):
            matrix.append_curated_rows(rows, [row])
        for field, value in (("source_revision", "0" * 40), ("source_expression", "invented()"), ("id", "new")):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "preserve"):
                    matrix.apply_evidence(rows, {row["id"]: {field: value}})
        reviewed = matrix.apply_evidence(rows, {row["id"]: {
            "status": "SOURCE_MAPPED", "semantic_mapping_evidence": "docs/review.md#source"}})
        promoted = next(item for item in reviewed if item["id"] == row["id"])
        self.assertEqual(promoted["status"], "SOURCE_MAPPED")
        self.assertEqual(row["status"], "NOT_MAPPED")

    def test_invalid_source_metadata_and_locations_are_rejected(self):
        row = next(row for row in self.build() if row["row_kind"] == "screen")
        for field, value in (("source_repository", "other/repo"), ("source_url", "https://example.com/guess"),
                ("source_line", "-1"), ("source_column", "0"), ("domain", "COMPLETE")):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    matrix.validate_rows([dict(row, **{field: value})])

    def test_explicit_curated_owner_requirements_can_cite_pinned_mfierp_provenance(self):
        revision = "8d4d22eaea6caaed28a98a801bd0596907cc0d3a"
        row = matrix.curated_obligation("owner-erp", "D18", "Verify both editions",
            row_kind="owner_requirement", source_repository="nandahtoon/MFIERP", source_revision=revision,
            source_path="docs/ODOO_20_EDITION_CRM_ACCOUNTING_ADR.md", source_line="15",
            extraction_evidence="CURATED_OWNER_REQUIREMENT")
        row["source_url"] = f"https://github.com/nandahtoon/MFIERP/blob/{revision}/{row['source_path']}#L15"
        matrix.validate_rows([row])
        row["source_revision"] = "main"
        with self.assertRaisesRegex(ValueError, "exact revision"):
            matrix.validate_rows([row])

    def test_summary_counts_obligations_without_a_completion_percentage(self):
        rows = self.build()
        summary = matrix.summarize(rows)
        self.assertEqual(summary, matrix.matrix_summary(rows))
        self.assertEqual(summary["by_status"], {"NOT_MAPPED": len(rows)})
        self.assertIn("limitations", summary)
        self.assertNotIn("completion_percentage", summary)
        self.assertIn("provisional", json.dumps(summary))

    def test_cli_writes_consistent_csv_and_summary_with_explicit_curated_rows(self):
        inputs = {"tree": self.tree, "endpoints": self.inventory, "catalog": self.catalog,
            "curated": [matrix.curated_obligation("cli-review", "D18", "Review an explicit obligation")]}
        args = [sys.executable, str(Path(matrix.__file__)), "--source-root", str(self.root)]
        for flag, value in inputs.items():
            path = self.root / (flag + ".json")
            path.write_text(json.dumps(value), encoding="utf-8")
            args.extend(["--" + flag, str(path)])
        output = self.root / "output/matrix.csv"
        summary_path = self.root / "output/summary.json"
        args.extend(["--output", str(output), "--summary", str(summary_path)])
        result = subprocess.run(args, capture_output=True, text=True, check=True, cwd=self.root)
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        self.assertEqual(summary_path.read_bytes(), (json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode())
        self.assertEqual(summary, json.loads(result.stdout))
        with output.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(summary["rows"], len(rows))
        self.assertEqual(summary["by_status"], {"NOT_MAPPED": len(rows)})
        self.assertTrue(any(row["id"] == "CURATED-cli-review" for row in rows))

    def test_tracked_csv_curated_rows_and_canonical_summary_are_consistent_offline(self):
        parity_dir = Path(__file__).resolve().parents[1] / "docs/parity"
        csv_path = parity_dir / "FULL_FUNCTIONAL_MATRIX.csv"
        curated = json.loads((parity_dir / "CURATED_WORKFLOWS.json").read_text(encoding="utf-8"))
        summary = json.loads((parity_dir / "FULL_FUNCTIONAL_MATRIX.summary.json").read_text(encoding="utf-8"))
        self.assertEqual((parity_dir / "FULL_FUNCTIONAL_MATRIX.summary.json").read_bytes(),
            (json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode())
        with csv_path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            self.assertEqual(tuple(reader.fieldnames), matrix.FIELDNAMES)
            rows = list(reader)
        matrix.validate_rows(rows)
        matrix.validate_rows(curated)
        curated_by_id = {row["id"]: row for row in curated}
        actual_curated = {row["id"]: row for row in rows if row["extraction_evidence"].startswith("CURATED_")}
        self.assertEqual(actual_curated, curated_by_id)
        for row in rows:
            if row["id"] in curated_by_id:
                continue
            self.assertEqual(row["id"], matrix.stable_id(row["row_kind"], row["source_path"],
                row["source_line"], row["source_column"], row["source_expression"]))
            self.assertEqual(row["status"], "NOT_MAPPED")
        for key, value in matrix.summarize(rows).items():
            self.assertEqual(summary[key], value, key)
        manifest = summary["source_manifest"]
        expected = {"tree_input_kind": "CANONICAL_COMPLETE_REPOSITORY_TREE",
            "source_repository": matrix.SOURCE_REPOSITORY, "source_revision": matrix.SOURCE_REVISION,
            "root_tree_sha": matrix._source_helper.PINNED_TREE_SHA, "root_tree_identity_verified": True,
            "repository_entries": 3998, "repository_blobs": 3096,
            "expected_files": 2863, "verified_files": 2863, "missing_files": [],
            "repository_blobs_outside_extraction_scope": 233, "app_only_extraction": True,
            "extension_scope": list(matrix.SOURCE_SUFFIXES),
            "verified_by_extension": {".ts": 1373, ".html": 743, ".scss": 747}}
        for key, value in expected.items():
            self.assertEqual(manifest[key], value, key)
        self.assertIn("src/app", manifest["extraction_scope"])
        self.assertIn("not extracted", manifest["extraction_scope"])
        regenerated = self.root / "tracked-matrix.csv"
        matrix.write_matrix(rows, regenerated)
        self.assertEqual(csv_path.read_bytes(), regenerated.read_bytes())


if __name__ == "__main__":
    unittest.main()
