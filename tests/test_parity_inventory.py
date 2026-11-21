"""Regression evidence for route comparison; candidate matches are not UAT."""
import importlib.util
from pathlib import Path
import unittest

module = importlib.util.spec_from_file_location("inventory", Path(__file__).resolve().parents[1] / "scripts/inventory_mifos_parity.py")
parity = importlib.util.module_from_spec(module)
module.loader.exec_module(parity)


class ParityInventoryTests(unittest.TestCase):
    def compare(self, source_path, api_path, parameters):
        catalog = {"api_version": "synthetic", "source_sha256": "synthetic", "capabilities": [{
            "key": "synthetic", "method": "GET", "path": api_path, "parameters": parameters, "blocked": ""}]}
        calls = [{"path": source_path, "method": "GET", "source": "src/app/loans/loans.service.ts", "line": 1}]
        return parity.inventory(calls, catalog, "synthetic/example", "synthetic")["calls"][0]

    def test_named_preview_is_not_a_numeric_transaction_lookup(self):
        result = self.compare("/loans/${loanId}/transactions/reage-preview", "/v1/loans/{loanId}/transactions/{transactionId}", [
            {"name": name, "in": "path", "schema": {"type": "integer"}} for name in ["loanId", "transactionId"]])
        self.assertEqual(result["status"], "NOT_IN_DEPLOYED_OPENAPI")
        self.assertEqual(result["capabilities"], [])

    def test_concrete_documents_match_the_typed_generic_entity_route(self):
        result = self.compare("/clients/${clientId}/documents", "/v1/{entityType}/{entityId}/documents", [
            {"name": "entityType", "in": "path", "schema": {"type": "string"}},
            {"name": "entityId", "in": "path", "schema": {"type": "integer"}}])
        self.assertEqual(result["status"], "TYPED_CONTRACT_CANDIDATE")
        self.assertFalse(result["live_uat_verified"])

    def test_fixed_share_contract_is_not_a_loan_contract(self):
        result = self.compare("/accounts/loan/${id}", "/v1/accounts/{type}/{id}", [
            {"name": "type", "in": "path", "schema": {"type": "string", "enum": ["share"]}},
            {"name": "id", "in": "path", "schema": {"type": "integer"}}])
        self.assertEqual(result["status"], "NOT_IN_DEPLOYED_OPENAPI")

    def test_dynamic_resource_remains_a_review_item(self):
        result = self.compare("/${productType}/${id}", "/v1/loans/{id}", [
            {"name": "id", "in": "path", "schema": {"type": "integer"}}])
        self.assertEqual(result["status"], "DYNAMIC_RESOURCE_REQUIRES_REVIEW")
