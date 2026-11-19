# SPDX-License-Identifier: LGPL-3.0-or-later
import importlib.util
import unittest
import os
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("workspace", ROOT / "addons/mfierp/services/workspace.py")
workspace = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workspace)


class WorkspaceContracts(unittest.TestCase):
    def request(self, key, path=None, query=None, body=None):
        return {"contract_digest": workspace.contract_digest(key), "path": path or {}, "query": query or {}, "body": body}

    def find(self, method, path):
        return next(c["key"] for c in workspace.capabilities().values() if c["method"] == method and c["path"] == path)

    def test_nested_client_identifier_contract_and_route(self):
        key = self.find("POST", "/v1/clients/{clientId}/identifiers")
        result = workspace.build_request(key, self.request(key, {"clientId": 7}, body={
            "documentTypeId": 3, "documentKey": "SYNTHETIC-123", "description": "Synthetic test"}))
        self.assertEqual(result[:3], ("POST", "clients/7/identifiers", {}))
        self.assertEqual(result[3]["documentTypeId"], 3)

    def test_unknown_nested_fields_and_mistyped_ids_fail_closed(self):
        key = self.find("POST", "/v1/clients/{clientId}/identifiers")
        for path, body in [({"clientId": "7"}, {}), ({"clientId": 7}, {"command": "delete"})]:
            with self.assertRaises(ValueError):
                workspace.build_request(key, self.request(key, path, body=body))

    def test_contract_change_and_undeclared_query_block_dispatch(self):
        key = self.find("GET", "/v1/clients")
        request = self.request(key)
        request["contract_digest"] = "changed"
        with self.assertRaises(ValueError):
            workspace.build_request(key, request)
        with self.assertRaises(ValueError):
            workspace.build_request(key, self.request(key, query={"arbitrarySql": "SELECT 1"}))

    def test_page_bounds(self):
        key = self.find("GET", "/v1/clients")
        for query in [{"limit": 1001}, {"offset": -1}]:
            with self.assertRaises(ValueError):
                workspace.build_request(key, self.request(key, query=query))

    def test_v2_contract_keeps_a_separate_fixed_version(self):
        key = self.find("GET", "/v2/groups")
        self.assertEqual(workspace.specification(key)["api_version"], "v2")
        result = workspace.build_request(key, self.request(key))
        self.assertEqual(result[:2], ("GET", "groups"))

    def test_application_contract_does_not_offer_arbitrary_datatable_payloads(self):
        entry = next(c for c in workspace.capabilities().values() if c["key"].endswith("__application"))
        result = workspace.build_request(entry["key"], self.request(entry["key"], body={"clientId": 7, "productId": 1}))
        self.assertEqual(result[:3], ("POST", "loans", {}))
        with self.assertRaises(ValueError):
            workspace.build_request(entry["key"], self.request(entry["key"], body={"datatables": [{"data": {"anything": 1}}]}))

    def test_unsupported_commands_never_accept_a_freeform_command(self):
        key = self.find("POST", "/v1/loans/{loanId}")
        with self.assertRaises(ValueError):
            workspace.build_request(key, self.request(key, {"loanId": 1}, {"command": "disburse"}, {}))

    def test_array_and_enum_validation(self):
        schema = {"type": "array", "items": {"type": "object", "required": ["amount"], "properties": {
            "amount": {"type": "number", "minimum": 0}, "kind": {"type": "string", "enum": ["fee", "penalty"]}}}}
        workspace.validate([{"amount": 12.5, "kind": "fee"}], schema)
        for value in [[{"kind": "fee"}], [{"amount": float("nan")}], [{"amount": 1, "kind": "invented"}]]:
            with self.assertRaises(ValueError):
                workspace.validate(value, schema)

    def test_command_variant_cannot_be_substituted_or_add_other_action_fields(self):
        entry = next(c for c in workspace.capabilities().values() if c.get("source_form")
            and c["path"] == "/v1/clients/{clientId}" and c["key"].endswith("__reactivate"))
        key = entry["key"]
        body = {"reactivationDate": "2026-11-18", "dateFormat": "yyyy-MM-dd", "locale": "en"}
        result = workspace.build_request(key, self.request(key, {"clientId": 7}, {"command": "reactivate"}, body))
        self.assertEqual(result[:3], ("POST", "clients/7", {"command": "reactivate"}))
        with self.assertRaises(ValueError):
            workspace.build_request(key, self.request(key, {"clientId": 7}, {"command": "reject"}, body))
        with self.assertRaises(ValueError):
            workspace.build_request(key, self.request(key, {"clientId": 7}, {"command": "reactivate"}, {**body, "rejectionReasonId": 1}))

    def test_all_source_variants_have_fixed_command_and_valid_fields(self):
        entries = [c for c in workspace.capabilities().values() if c.get("source_form")]
        self.assertGreaterEqual(len(entries), 40)
        for entry in entries:
            command = next(p for p in entry["parameters"] if p["name"] == "command")
            self.assertEqual(len(command["schema"]["enum"]), 1)
            schema = entry["body"]
            self.assertTrue(set(schema["required"]) <= schema["properties"].keys())

    def test_path_traversal_and_url_parameters_are_rejected(self):
        schema = {"type": "object", "properties": {"value": {"type": "string"}}}
        with self.assertRaises(ValueError):
            workspace.validate({"value": {"nested": "arbitrary"}}, schema)
        # Type-valid text identifiers still cannot become routes or query strings.
        entry = next(c for c in workspace.capabilities().values() if not c["blocked"] and c["method"] == "GET"
            and len(c["parameters"]) == 1 and c["parameters"][0]["in"] == "path" and c["parameters"][0]["schema"].get("type") == "string")
        name = entry["parameters"][0]["name"]
        with self.assertRaises(ValueError):
            workspace.build_request(entry["key"], self.request(entry["key"], {name: "../users?x=1"}))

    def test_secrets_are_bound_without_appearing_in_reviewed_data(self):
        with patch.dict(os.environ, {"MFIERP_SECRET_BINDING_KEY": "synthetic-signing-key-at-least-32-characters",
                "MFIERP_TEST_USER_PASSWORD": "synthetic-password-one"}):
            marker = workspace.bind_secret("MFIERP_TEST_USER_PASSWORD", "connection:workflow:request")
            self.assertNotIn("synthetic-password-one", str(marker))
            self.assertEqual(workspace.reveal_secret(marker), "synthetic-password-one")
            os.environ["MFIERP_TEST_USER_PASSWORD"] = "synthetic-password-two"
            with self.assertRaises(ValueError):
                workspace.reveal_secret(marker)

    def test_signing_key_is_not_an_accepted_password_reference(self):
        with self.assertRaises(ValueError):
            workspace.bind_secret("MFIERP_SECRET_BINDING_KEY", "context")
