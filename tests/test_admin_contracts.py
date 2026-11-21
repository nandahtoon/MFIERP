# SPDX-License-Identifier: LGPL-3.0-or-later
import importlib.util
import unittest
from copy import deepcopy
from pathlib import Path

spec = importlib.util.spec_from_file_location("workspace", Path(__file__).resolve().parents[1] / "addons/mfierp/services/workspace.py")
workspace = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workspace)


class AdministrativeContracts(unittest.TestCase):
    def variant(self, path, suffix):
        return next(c for c in workspace.capabilities().values() if c["path"] == path and c["key"].endswith("__" + suffix))

    def build(self, entry, path, body, query=None):
        return workspace.build_request(entry["key"], {"contract_digest": workspace.contract_digest(entry["key"]),
            "path": path, "query": query or {}, "body": body})

    def test_standing_update_cannot_change_transfer_accounts_or_command(self):
        entry = self.variant("/v1/standinginstructions/{standingInstructionId}", "update")
        body = {"priority": 1, "status": 2, "validFrom": "2026-11-19", "validTill": "2027-11-19",
            "recurrenceType": 1, "recurrenceFrequency": 0, "recurrenceInterval": 1, "amount": 0.25,
            "recurrenceOnMonthDay": "19 November", "monthDayFormat": "dd MMMM"}
        path, query = {"standingInstructionId": 7}, {"command": "update"}
        self.assertEqual(self.build(entry, path, body, query)[:2], ("PUT", "standinginstructions/7"))
        for changed in [{**body, "fromAccountId": 9}, {**body, "name": "unreviewed"}, {**body, "amount": 0},
                {**body, "priority": 5}, {**body, "recurrenceFrequency": 4}, {**body, "monthDayFormat": "MM-dd"},
                {**body, "recurrenceOnMonthDay": "2026-11-19"}]:
            with self.assertRaises(ValueError):
                self.build(entry, path, changed, query)
        with self.assertRaises(ValueError):
            self.build(entry, path, body, {"command": "delete"})

    def test_provisioning_uses_unique_explicit_products_and_category_definitions(self):
        body = {"criteriaName": "Synthetic Criteria", "loanProducts": [{"id": 3}], "definitions": [{"categoryId": 1,
            "minAge": 0, "maxAge": 30, "provisioningPercentage": 2.5, "liabilityAccount": 8, "expenseAccount": 9}]}
        for suffix, path in [("createCriteria", "/v1/provisioningcriteria"), ("updateCriteria", "/v1/provisioningcriteria/{criteriaId}")]:
            entry = self.variant(path, suffix)
            self.assertTrue(entry["admin_only"])
            target = {"criteriaId": 7} if suffix == "updateCriteria" else {}
            self.build(entry, target, body)
            for changed in [{**body, "loanProducts": []}, {**body, "loanProducts": [{"id": 3}, {"id": 3}]},
                    {**body, "definitions": body["definitions"] * 2}, {**body, "definitions": []},
                    {**body, "loanProducts": [{"id": 3, "arbitrary": {"nested": True}}]}]:
                with self.assertRaises(ValueError):
                    self.build(entry, target, changed)
            for field, value in [("minAge", -1), ("maxAge", 0), ("provisioningPercentage", -1), ("expenseAccount", 0),
                    ("categoryId", True), ("minAge", 30)]:
                changed = deepcopy(body)
                changed["definitions"][0][field] = value
                with self.assertRaises(ValueError):
                    self.build(entry, target, changed)

    def test_dividend_creation_and_approval_are_separate_reviewed_actions(self):
        create = self.variant("/v1/shareproduct/{productId}/dividend", "createDividend")
        body = {"dividendPeriodStartDate": "2026-01-01", "dividendPeriodEndDate": "2026-11-19", "dividendAmount": 12.5}
        self.build(create, {"productId": 3}, body)
        with self.assertRaises(ValueError):
            self.build(create, {"productId": 3}, {**body, "dividendAmount": 0})
        approve = self.variant("/v1/shareproduct/{productId}/dividend/{dividendId}", "approve")
        self.assertTrue(create["require_reconciliation"] and approve["require_reconciliation"])
        self.assertTrue(create["capture_subresource"])
        self.assertTrue(approve["admin_only"])
        self.build(approve, {"productId": 3, "dividendId": 19}, {}, {"command": "approve"})
        with self.assertRaises(ValueError):
            self.build(approve, {"productId": 3, "dividendId": 19}, {"dividendId": 20}, {"command": "approve"})

    def test_scheduler_commands_are_fixed_and_manager_only(self):
        for command in ["start", "stop"]:
            entry = self.variant("/v1/scheduler", command)
            self.assertTrue(entry["admin_only"])
            self.assertEqual(self.build(entry, {}, {}, {"command": command})[:2], ("POST", "scheduler"))
            with self.assertRaises(ValueError):
                self.build(entry, {}, {}, {"command": "executeJob"})
            with self.assertRaises(ValueError):
                self.build(entry, {}, {"customParameters": []}, {"command": command})
        read = workspace.specification("get_retrieveSchedulerStatus")
        self.assertTrue(read["admin_only"])
        exceptions = [entry for entry in workspace.capabilities().values() if entry.get("reconciliation_without_resource")]
        self.assertEqual({entry["key"].rsplit("__", 1)[-1] for entry in exceptions}, {"start", "stop"})
        self.assertTrue(all(entry["path"] == "/v1/scheduler" and entry["admin_only"] for entry in exceptions))

    def test_bulk_reassignment_is_explicit_unique_and_uses_different_officers(self):
        entry = self.variant("/v1/loans/loanreassignment", "reassignLoans")
        self.assertTrue(entry["admin_only"] and entry["require_reconciliation"])
        body = {"fromLoanOfficerId": 1, "toLoanOfficerId": 2, "assignmentDate": "2026-11-19", "loans": [7, 8]}
        self.assertEqual(self.build(entry, {}, body)[:2], ("POST", "loans/loanreassignment"))
        for changed in [{**body, "loans": []}, {**body, "loans": [7, 7]}, {**body, "loans": [{"id": 7}]},
                {**body, "loans": [True]}, {**body, "toLoanOfficerId": 1}, {**body, "officeId": 3}]:
            with self.assertRaises(ValueError):
                self.build(entry, {}, changed)

    def test_holiday_activation_has_no_body_and_savings_tax_is_boolean_only(self):
        holiday = self.variant("/v1/holidays/{holidayId}", "activate")
        self.assertTrue(holiday["admin_only"] and holiday["require_reconciliation"])
        self.assertIsNone(self.build(holiday, {"holidayId": 9}, None, {"command": "activate"})[3])
        with self.assertRaises(ValueError):
            self.build(holiday, {"holidayId": 9}, {"fromDate": "2026-11-19"}, {"command": "activate"})
        tax = self.variant("/v1/savingsaccounts/{accountId}", "updateWithHoldTax")
        for value in [False, True]:
            self.assertEqual(self.build(tax, {"accountId": 7}, {"withHoldTax": value}, {"command": "updateWithHoldTax"})[3], {"withHoldTax": value})
        for body in [{}, {"withHoldTax": "false"}, {"withHoldTax": 0}, {"withHoldTax": False, "taxGroupId": 2}]:
            with self.assertRaises(ValueError):
                self.build(tax, {"accountId": 7}, body, {"command": "updateWithHoldTax"})

    def test_subresource_ids_preserve_payout_identity_without_trusting_malformed_references(self):
        self.assertEqual(workspace.subresource_reference({"resourceId": 3, "subResourceId": 19}), 19)
        self.assertIsNone(workspace.subresource_reference({"commandId": 99}))
        for value in [True, 0, -1, "19", [], {}]:
            with self.assertRaises(ValueError):
                workspace.subresource_reference({"subResourceId": value})

    def test_all_supported_audit_versions_use_protected_metadata_reads(self):
        entries = [entry for entry in workspace.capabilities().values() if entry["method"] == "GET"
            and entry["path"] in {"/v1/audits", "/v1/audits/{auditId}", "/v2/audits", "/v1/makercheckers"}]
        self.assertEqual(len(entries), 4)
        self.assertTrue(all(entry["admin_only"] and entry.get("response_mode") == "audit_metadata" for entry in entries))
