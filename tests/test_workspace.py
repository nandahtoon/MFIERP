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
    def variant(self, path, command, method="POST"):
        return next(c for c in workspace.capabilities().values() if c["path"] == path and c["method"] == method
            and c.get("source_form") and c["key"].endswith("__" + command))

    def test_deposit_cash_routes_cannot_turn_into_adjustments(self):
        for deposit in ["fixed", "recurring"]:
            name = deposit + "DepositAccountId"
            entry = self.variant(f"/v1/{deposit}depositaccounts/{{{name}}}/transactions", "deposit")
            key = entry["key"]
            body = {"transactionDate": "2026-11-19", "transactionAmount": 2.75, "paymentTypeId": 3}
            result = workspace.build_request(key, self.request(key, {name: 12}, {"command": "deposit"}, body))
            self.assertEqual(result[:2], ("POST", f"{deposit}depositaccounts/12/transactions"))
            for path in [{name: "undefined"}, {name: 0}, {name: 12, "transactionId": 44}]:
                with self.assertRaises(ValueError):
                    workspace.build_request(key, self.request(key, path, {"command": "deposit"}, body))
            with self.assertRaises(ValueError):
                workspace.build_request(key, self.request(key, {name: 12}, {"command": "deposit"}, {**body, "note": "not transmitted by source"}))

    def test_deposit_reversal_amount_is_fixed_and_requires_transaction_id(self):
        for deposit in ["fixed", "recurring"]:
            name = deposit + "DepositAccountId"
            entry = self.variant(f"/v1/{deposit}depositaccounts/{{{name}}}/transactions/{{transactionId}}", "undo")
            key = entry["key"]
            body = {"transactionDate": "2026-11-19", "transactionAmount": 0}
            path = {name: 12, "transactionId": 44}
            result = workspace.build_request(key, self.request(key, path, {"command": "undo"}, body))
            self.assertEqual(result[1], f"{deposit}depositaccounts/12/transactions/44")
            for changed in [{**body, "transactionAmount": 1}, {"transactionDate": "2026-11-19"}]:
                with self.assertRaises(ValueError):
                    workspace.build_request(key, self.request(key, path, {"command": "undo"}, changed))

    def test_recurring_transaction_template_commands_are_separate_reads(self):
        path = "/v1/recurringdepositaccounts/{recurringDepositAccountId}/transactions/template"
        for command in ["deposit", "withdrawal"]:
            entry = self.variant(path, command, "GET")
            result = workspace.build_request(entry["key"], self.request(entry["key"], {"recurringDepositAccountId": 12}, {"command": command}))
            self.assertEqual(result[0], "GET")
            self.assertIsNone(result[3])
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

    def test_reschedule_approval_and_rejection_have_separate_date_contracts(self):
        for command, date_field, forbidden in [("approve", "approvedOnDate", "rejectedOnDate"), ("reject", "rejectedOnDate", "approvedOnDate")]:
            entry = next(c for c in workspace.capabilities().values() if c["path"] == "/v1/rescheduleloans/{scheduleId}"
                and c["key"].endswith("__" + command))
            key = entry["key"]
            result = workspace.build_request(key, self.request(key, {"scheduleId": 3}, {"command": command}, {date_field: "2026-11-19"}))
            self.assertEqual(result[:2], ("POST", "rescheduleloans/3"))
            with self.assertRaises(ValueError):
                workspace.build_request(key, self.request(key, {"scheduleId": 3}, {"command": command}, {forbidden: "2026-11-19"}))

    def test_fractional_charge_payment_and_exclusive_bounds(self):
        entry = next(c for c in workspace.capabilities().values() if c["path"] == "/v1/clients/{clientId}/charges/{chargeId}"
            and c["key"].endswith("__paycharge"))
        key = entry["key"]
        body = {"amount": 2.75, "transactionDate": "2026-11-19"}
        result = workspace.build_request(key, self.request(key, {"clientId": 7, "chargeId": 9}, {"command": "paycharge"}, body))
        self.assertEqual(result[3]["amount"], 2.75)
        for value in [0, -1, float("inf"), True]:
            with self.assertRaises(ValueError):
                workspace.build_request(key, self.request(key, {"clientId": 7, "chargeId": 9}, {"command": "paycharge"}, {**body, "amount": value}))
        for schema in [{"type": "number", "maximum": 1, "exclusiveMaximum": True}, {"type": "number", "exclusiveMaximum": 1}]:
            with self.assertRaises(ValueError):
                workspace.validate(1, schema)

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
            if schema is not None:
                self.assertTrue(set(schema["required"]) <= schema["properties"].keys())

    def test_administrative_no_body_command_is_fixed_and_privileged(self):
        entry = next(c for c in workspace.capabilities().values() if c.get("source_form")
            and c["path"] == "/v1/surveys/{id}" and c["key"].endswith("__activate"))
        result = workspace.build_request(entry["key"], self.request(entry["key"], {"id": 7}, {"command": "activate"}))
        self.assertIsNone(result[3])
        self.assertTrue(entry["admin_only"])

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
                "MFIERP_WORKFLOW_SECRET_TEST_USER_PASSWORD": "synthetic-password-one"}):
            marker = workspace.bind_secret("MFIERP_WORKFLOW_SECRET_TEST_USER_PASSWORD", "connection:workflow:request")
            self.assertNotIn("synthetic-password-one", str(marker))
            self.assertEqual(workspace.reveal_secret(marker), "synthetic-password-one")
            os.environ["MFIERP_WORKFLOW_SECRET_TEST_USER_PASSWORD"] = "synthetic-password-two"
            with self.assertRaises(ValueError):
                workspace.reveal_secret(marker)

    def test_signing_key_is_not_an_accepted_password_reference(self):
        for reference in ["MFIERP_SECRET_BINDING_KEY", "MFIERP_DB_PASSWORD", "MFIERP_DEFAULT_PASSWORD"]:
            with self.assertRaises(ValueError):
                workspace.bind_secret(reference, "context")
