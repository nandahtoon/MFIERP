# SPDX-License-Identifier: LGPL-3.0-or-later
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"addons/mfierp/services/{name}.py")
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


projection = module("collection_sheet")
workspace = module("workspace")


class CollectionContracts(unittest.TestCase):
    def entry(self, suffix):
        return next(c for c in workspace.capabilities().values() if c["key"].endswith("__" + suffix))

    def envelope(self, entry, body, path=None):
        return {"contract_digest": workspace.contract_digest(entry["key"]), "path": path or {}, "query": {
            p["name"]: p["schema"]["enum"][0] for p in entry["parameters"] if p["in"] == "query" and p.get("required")}, "body": body}

    def test_projection_preserves_remote_amounts_and_removes_unneeded_fields(self):
        result = projection.project_preview({"clients": [{"clientName": "Synthetic", "loans": [{"loanId": 7,
            "totalDue": 12.5, "chargesDue": 0.75, "password": "must-not-retain"}]}]})
        self.assertEqual(result["rows"][0]["due"], 12.5)
        self.assertEqual(result["rows"][0]["charges"], 0.75)
        self.assertNotIn("must-not-retain", str(result))
        self.assertNotIn("total", result["rows"][0])

    def test_preview_is_bounded_and_invalid_amounts_are_rejected(self):
        data = {"clients": [{"loans": [{"loanId": i, "totalDue": 1} for i in range(1, 510)]}]}
        result = projection.project_preview(data)
        self.assertEqual(len(result["rows"]), 500)
        self.assertTrue(result["truncated"])
        with self.assertRaises(ValueError):
            projection.project_preview({"clients": [{"loans": [{"loanId": 7, "totalDue": "invented"}]}]})

    def test_posting_rejects_empty_duplicate_or_mismatched_collections(self):
        entry = self.entry("saveCollectionSheet")
        body = {"transactionDate": "2026-11-19", "actualDisbursementDate": "2026-11-19",
            "bulkDisbursementTransactions": {"bulkRepaymentTransactions": [{"loanId": 7, "transactionAmount": 12.5}]}}
        workspace.build_request(entry["key"], self.envelope(entry, body))
        invalid = [{**body, "bulkDisbursementTransactions": {}}, {**body, "actualDisbursementDate": "2026-11-20"},
            {**body, "bulkDisbursementTransactions": {"bulkRepaymentTransactions": [{"loanId": 7, "transactionAmount": 1}, {"loanId": 7, "transactionAmount": 2}]}}]
        for changed in invalid:
            with self.assertRaises(ValueError):
                workspace.build_request(entry["key"], self.envelope(entry, changed))

    def test_attendance_uses_published_option_objects_and_unique_clients(self):
        entry = self.entry("recordGroupsAttendance")
        body = {"calendarId": 3, "meetingDate": "2026-11-19", "clientsAttendance": [{"clientId": 7, "attendanceType": {"id": 1}}]}
        path = {"entityType": "groups", "entityId": 8}
        workspace.build_request(entry["key"], self.envelope(entry, body, path))
        for rows in [[{"clientId": 7, "attendanceType": 1}], [{"clientId": 7, "attendanceType": {"id": 1}}, {"clientId": 7, "attendanceType": {"id": 2}}]]:
            with self.assertRaises(ValueError):
                workspace.build_request(entry["key"], self.envelope(entry, {**body, "clientsAttendance": rows}, path))
