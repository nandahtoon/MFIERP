# SPDX-License-Identifier: LGPL-3.0-or-later
import importlib.util
import json
import unittest
from copy import deepcopy
from pathlib import Path

spec = importlib.util.spec_from_file_location("audit_metadata", Path(__file__).resolve().parents[1]
    / "addons/mfierp/services/audit_metadata.py")
audit_metadata = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_metadata)


class AuditMetadataProjection(unittest.TestCase):
    def test_detail_omits_submitted_payload_and_unknown_nested_data_without_mutating_source(self):
        secret = "synthetic-do-not-persist"
        source = {"id": 7, "actionName": "CREATE", "entityName": "USER", "resourceId": 19,
            "maker": "maker", "checker": None, "madeOnDate": "2026-11-19T17:00:00Z",
            "processingResult": "processed", "commandAsJson": json.dumps({"password": secret}),
            "url": "https://example.invalid/" + secret, "ip": "192.0.2.1", "clientName": secret,
            "groupName": secret, "unknown": {"credentials": secret}, "password": secret}
        original = deepcopy(source)
        projected = audit_metadata.project_metadata(source)
        self.assertEqual(projected, {"pageItems": [{"id": 7, "actionName": "CREATE", "entityName": "USER",
            "resourceId": 19, "maker": "maker", "madeOnDate": "2026-11-19T17:00:00Z",
            "processingResult": "processed"}], "truncated": False})
        self.assertNotIn(secret, json.dumps(projected))
        self.assertEqual(source, original)

    def test_list_and_page_keep_resource_references_with_minimal_account_labels(self):
        row = {"id": 7, "subresourceId": 3, "clientId": 8, "loanId": 9, "officeId": 1, "groupId": 2,
            "savingsAccountId": 10, "productId": 11, "officeName": "Synthetic branch", "loanAccountNo": "L9",
            "savingsAccountNo": "S10", "transactionId": "19", "resourceExternalId": "resource-9",
            "subresourceExternalId": "sub-3", "loanExternalId": "loan-9", "submittedOfficeId": 1,
            "submittedGroupId": 2, "submittedClientId": 8, "submittedLoanId": 9, "submittedSavingsAccountId": 10,
            "submittedProductId": 11, "submittedResourceId": 9, "submittedSubresourceId": 3,
            "submittedTransactionId": "19", "submittedResourceExternalId": "resource-9",
            "submittedSubresourceExternalId": "sub-3", "submittedLoanExternalId": "loan-9"}
        self.assertEqual(audit_metadata.project_metadata([row]), {"pageItems": [row], "truncated": False})
        self.assertEqual(audit_metadata.project_metadata({"pageItems": [row], "totalFilteredRecords": 4,
            "other": {"commandAsJson": "excluded"}}), {"pageItems": [row], "truncated": False, "totalFilteredRecords": 4})
        self.assertEqual(audit_metadata.project_metadata({"pageItems": [], "totalFilteredRecords": 0}),
            {"pageItems": [], "truncated": False, "totalFilteredRecords": 0})

    def test_rows_and_scalar_strings_have_explicit_bounds(self):
        rows = [{"id": index + 1, "maker": "m" * 300, "madeOnDate": "d" * 1100} for index in range(201)]
        rows[-1] = {"id": False, "commandAsJson": "not inspected beyond the row cap"}
        projected = audit_metadata.project_metadata(rows)
        self.assertEqual(len(projected["pageItems"]), 200)
        self.assertTrue(projected["truncated"])
        self.assertEqual(len(projected["pageItems"][0]["maker"]), 250)
        self.assertEqual(len(projected["pageItems"][0]["madeOnDate"]), 1000)

    def test_malformed_shapes_identifiers_and_declared_metadata_fail_closed(self):
        for source in [None, False, 0, "payload", {}, {"commandAsJson": "secret"}, {"pageItems": {}},
                {"pageItems": None}, [None], [{"id": 1}, []]]:
            with self.subTest(source=source), self.assertRaises(ValueError):
                audit_metadata.project_metadata(source)
        for name in ["id", "resourceId", "submittedLoanId"]:
            for value in [False, True, 0, -1, 1.0, "1", [], {}, (1 << 63)]:
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    audit_metadata.project_metadata({"id": 7, name: value})
        for name in ["maker", "processingResult", "madeOnDate", "resourceExternalId"]:
            for value in [False, 0, [], {}, 1.5]:
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    audit_metadata.project_metadata({"id": 7, name: value})
        for count in [None, False, -1, 1.5, "2", (1 << 63)]:
            with self.subTest(count=count), self.assertRaises(ValueError):
                audit_metadata.project_metadata({"pageItems": [], "totalFilteredRecords": count})

    def test_optional_nulls_are_omitted_and_errors_do_not_copy_remote_values(self):
        self.assertEqual(audit_metadata.project_metadata({"id": 7, "checker": None, "checkedOnDate": None,
            "resourceId": None}), {"pageItems": [{"id": 7}], "truncated": False})
        with self.assertRaises(ValueError) as raised:
            audit_metadata.project_metadata({"id": "synthetic-secret"})
        self.assertNotIn("synthetic-secret", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
