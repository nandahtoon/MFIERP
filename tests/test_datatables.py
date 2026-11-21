# SPDX-License-Identifier: LGPL-3.0-or-later
import importlib.util
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("datatables", ROOT / "addons/mfierp/services/datatables.py")
datatables = importlib.util.module_from_spec(spec)
spec.loader.exec_module(datatables)
spec = importlib.util.spec_from_file_location("workspace", ROOT / "addons/mfierp/services/workspace.py")
workspace = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workspace)


def column(name, display="INTEGER", *, primary=False, nullable=True, **values):
    return {"columnName": name, "columnDisplayType": display, "columnType": display.lower(),
        "columnLength": 0, "isColumnPrimaryKey": primary, "isColumnNullable": nullable, "columnValues": [], **values}


def metadata(multi=False):
    return {"registeredTableName": "Client survey", "applicationTableName": "m_client", "columnHeaderData": [
        column("client_id", primary=not multi, nullable=False),
        *([column("id", primary=True, nullable=False)] if multi else []),
        column("Nickname", "STRING", nullable=False, columnLength=8), column("Visits"), column("Consent", "BOOLEAN"),
        column("Score", "DECIMAL"), column("Review Date", "DATE"), column("Category_cd_Type", "CODELOOKUP",
            columnValues=[{"id": 2, "value": "Second"}, {"id": 1, "value": "First"}]),
        column("created_at", "DATETIME"), column("updated_at", "DATETIME")]}


class DatatableContracts(unittest.TestCase):
    def request(self, data, action, body=None, row=None):
        path = {"datatable": data["registeredTableName"], "apptableId": 7}
        if row is not None:
            path["datatableId"] = row
        return workspace.build_spec_request(datatables.specification(data, action), {
            "contract_digest": "pinned", "path": path, "query": {"genericResultSet": True} if action == "read" else {},
            "body": body}, "pinned")

    def test_typed_columns_exclude_audit_and_parent_fields(self):
        compiled = datatables.compile_table(metadata())
        self.assertFalse(compiled["multi_row"])
        body = compiled["body"]
        self.assertEqual(body["required"], ["Nickname"])
        self.assertNotIn("client_id", body["properties"])
        self.assertNotIn("created_at", body["properties"])
        self.assertEqual(body["properties"]["Category_cd_Type"]["enum"], [1, 2])
        valid = {"Nickname": "Test", "Consent": False, "Score": -1.25, "Review Date": "2026-11-19", "Category_cd_Type": 2}
        self.assertEqual(self.request(metadata(), "create", valid)[:2], ("POST", "datatables/Client%20survey/7"))
        for changed in [{**valid, "client_id": 8}, {**valid, "created_at": "2026-11-19"}, {**valid, "Category_cd_Type": 3},
                {**valid, "Visits": True}, {**valid, "Nickname": "Too long name"}, {**valid, "Review Date": "invalid"}, {}]:
            with self.assertRaises(ValueError):
                self.request(metadata(), "create", changed)

    def test_multi_row_updates_and_deletes_cannot_delete_all(self):
        for action, method in [("update", "PUT"), ("delete", "DELETE")]:
            body = {"Nickname": "Test"} if action == "update" else None
            self.assertEqual(self.request(metadata(True), action, body, 19)[:2], (method, "datatables/Client%20survey/7/19"))
            with self.assertRaises(ValueError):
                self.request(metadata(True), action, body)
            with self.assertRaises(ValueError):
                self.request(metadata(), action, body, 19)
        self.assertEqual(self.request(metadata(), "delete")[:2], ("DELETE", "datatables/Client%20survey/7"))

    def test_unsupported_metadata_never_opens_arbitrary_payloads(self):
        for extra in [column("Payload", "TEXT", columnType="json"), column("Time", "DATETIME"),
                column("password", "STRING"), column("locale", "STRING"), column("Category", "CODELOOKUP")]:
            data = metadata()
            data["columnHeaderData"].append(extra)
            with self.assertRaises(ValueError):
                datatables.compile_table(data)
        for name in ["../clients", "clients%2f7", "a?b", "x#y", "a\r\nb", " spaces "]:
            with self.assertRaises(ValueError):
                datatables.compile_table({**metadata(), "registeredTableName": name})
        with self.assertRaises(ValueError):
            datatables.compile_table({**metadata(), "applicationTableName": "unreviewed"})

    def test_schema_digest_ignores_order_but_detects_contract_changes(self):
        data = metadata()
        reordered = deepcopy(data)
        reordered["columnHeaderData"].reverse()
        self.assertEqual(datatables.fingerprint(data), datatables.fingerprint(reordered))
        for key, value in [("columnLength", 20), ("isColumnNullable", True), ("columnDisplayType", "TEXT")]:
            changed = deepcopy(data)
            changed["columnHeaderData"][1][key] = value
            self.assertNotEqual(datatables.fingerprint(data), datatables.fingerprint(changed))

    def test_malformed_keys_and_options_fail_closed(self):
        for change in [lambda d: d["columnHeaderData"].append(d["columnHeaderData"][0]),
                lambda d: d["columnHeaderData"][0].update(isColumnPrimaryKey=False),
                lambda d: d["columnHeaderData"][1].update(isColumnNullable="false"),
                lambda d: d["columnHeaderData"][-3].update(columnValues=[{"id": True, "value": "bad"}])]:
            data = metadata()
            change(data)
            with self.assertRaises(ValueError):
                datatables.compile_table(data)

    def test_generic_response_projection_is_bounded_and_declared(self):
        result = {"columnHeaders": [{"columnName": "Nickname"}, {"columnName": "Consent"}],
            "data": [{"row": ["<script>", False]}] * 201, "unneeded": "discard"}
        preview = datatables.project_rows(result, metadata())
        self.assertEqual(len(preview["pageItems"]), 200)
        self.assertTrue(preview["truncated"])
        self.assertNotIn("unneeded", preview)
        for changed in [{**result, "columnHeaders": [{"columnName": "private"}]},
                {**result, "columnHeaders": [{"columnName": []}]}, {**result, "data": [{"row": [1]}]}]:
            with self.assertRaises(ValueError):
                datatables.project_rows(changed, metadata())


if __name__ == "__main__":
    unittest.main()
