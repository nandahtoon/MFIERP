# SPDX-License-Identifier: LGPL-3.0-or-later
from copy import deepcopy
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .test_workflows import TestMfierpWorkflows
from ..services.fineract import FineractError


@tagged("post_install", "-at_install")
class TestDatatableWorkflows(TestMfierpWorkflows):
    def _metadata(self, multi=False):
        def column(name, display, primary=False, nullable=True, **extra):
            return {"columnName": name, "columnDisplayType": display, "columnType": display.lower(), "columnLength": 0,
                "isColumnPrimaryKey": primary, "isColumnNullable": nullable, "columnValues": [], **extra}

        return {"registeredTableName": "Client extra", "applicationTableName": "m_client", "columnHeaderData": [
            column("client_id", "INTEGER", primary=not multi, nullable=False),
            *([column("id", "INTEGER", primary=True, nullable=False)] if multi else []),
            column("Nickname", "STRING", nullable=False, columnLength=50), column("Consent", "BOOLEAN"),
            column("Review Date", "DATE"), column("created_at", "DATETIME")]}

    def _discover(self, metadata=None, backend=None):
        backend = backend or self.backend
        with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
            client.return_value.request.return_value = [metadata or self._metadata()]
            backend.with_user(self.manager).action_refresh_datatables()
            client.return_value.request.assert_called_once_with("GET", "datatables")
        return self.env["mfierp.datatable"].search([("backend_id", "=", backend.id)], limit=1)

    def _request(self, table, action, user=None):
        user = user or self.maker
        request = self.env["mfierp.request"].with_user(user).create({"datatable_id": table.id,
            "datatable_action": action, "backend_id": table.backend_id.id})
        request.action_load()
        request.input_ids.filtered(lambda node: node.key == "apptableId").write({"integer_value": 7})
        if action in {"create", "update"}:
            request.input_ids.filtered(lambda node: node.key == "Nickname").write({"text_value": "Synthetic"})
            request.input_ids.filtered(lambda node: node.key == "Consent").write({"boolean_value": False, "included": True})
        if table.multi_row and action in {"update", "delete"}:
            request.input_ids.filtered(lambda node: node.key == "datatableId").write({"integer_value": 19})
        return request

    def test_discovery_is_manager_only_immutable_and_company_scoped(self):
        with self.assertRaises(AccessError):
            self.backend.with_user(self.maker).action_refresh_datatables()
        table = self._discover()
        self.assertTrue(table.executable)
        with self.assertRaises(AccessError):
            table.with_user(self.manager).write({"metadata_digest": "forged"})
        with self.assertRaises(AccessError):
            self.env["mfierp.datatable"].with_user(self.manager).create({"name": "Forged", "backend_id": self.backend.id})
        hidden = self.env["mfierp.datatable"].sudo().create({"name": "Hidden", "backend_id": self.other_backend.id})
        self.assertFalse(self.env["mfierp.datatable"].with_user(self.reader).search([("id", "=", hidden.id)]))
        with self.assertRaises(AccessError):
            hidden.with_user(self.reader).action_read_entries()
        with self.assertRaises(AccessError):
            table.with_user(self.reader).action_create_entry()
        with self.assertRaises(UserError):
            self.env["mfierp.request"].with_user(self.manager).create({"datatable_id": table.id, "backend_id": self.other_backend.id,
                "company_id": self.other_company.id})

    def test_native_crud_uses_reviewed_routes_and_independent_approval(self):
        for multi in [False, True]:
            metadata = self._metadata(multi)
            table = self._discover(metadata)
            for action, method in [("create", "POST"), ("update", "PUT"), ("delete", "DELETE")]:
                request = self._request(table, action)
                self.assertFalse(request.capability_id)
                self.assertEqual(request.method, method)
                command = self.env["mfierp.command"].browse(request.action_execute()["res_id"])
                self.assertEqual(command.state, "pending")
                self.assertEqual(command.datatable_id, table)
                with self.assertRaises(UserError):
                    command.with_user(self.maker).action_approve()
                command.with_user(self.checker).action_approve()
                command.write({"state": "dispatching"})
                with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
                    self._mock_provenance(client)
                    client.return_value.request.side_effect = lambda verb, *args, data=metadata, **kwargs: data if verb == "GET" else {"resourceId": 19}
                    command._dispatch()
                    self.assertEqual(command.state, "remote_pending")
                    self.assertTrue(command.response_received_at)
                    self.assertFalse(command.completed_at)
                    calls = client.return_value.request.call_args_list
                    self.assertEqual([call.args[0] for call in calls], ["GET", method])
                    expected = "datatables/Client%20extra/7" + ("/19" if multi and action != "create" else "")
                    self.assertEqual(calls[-1].args[1], expected)
                    if action != "delete":
                        self.assertFalse(calls[-1].kwargs["payload"]["Consent"])
                    else:
                        self.assertIsNone(calls[-1].kwargs["payload"])
                reconciliation = self.env["mfierp.reconcile"].with_user(self.manager).create({
                    "command_id": command.id, "outcome": "done", "resource_id": 19,
                    "note": "Synthetic record ID and independent audit note are insufficient evidence."})
                with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
                    with self.assertRaisesRegex(UserError, "authoritative readback verifier"):
                        reconciliation.action_record()
                    client.assert_not_called()
                self.assertEqual(command.state, "remote_pending")

    def test_reader_preview_is_escaped_and_does_not_persist_arbitrary_columns(self):
        table = self._discover()
        request = self._request(table, "read", self.reader)
        with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
            client.return_value.request.side_effect = [self._metadata(), {"columnHeaders": [{"columnName": "Nickname"}],
                "data": [{"row": ["<script>alert(1)</script>"]}], "private": "discard"}]
            request.action_execute()
            self.assertIn("&lt;script&gt;", str(request.result_html))
            self.assertNotIn("<script>", str(request.result_html))
            self.assertNotIn("private", request.result_text)
            self.assertEqual(client.return_value.request.call_args.kwargs["params"], {"genericResultSet": True})
        with self.assertRaises(AccessError):
            request.with_user(self.checker).input_ids[0].write({"included": False})

    def test_remote_metadata_drift_fails_before_business_write(self):
        table = self._discover()
        request = self._request(table, "create")
        command = self.env["mfierp.command"].browse(request.action_execute()["res_id"])
        command.with_user(self.checker).action_approve()
        command.write({"state": "dispatching"})
        changed = deepcopy(self._metadata())
        changed["columnHeaderData"][1]["columnLength"] = 100
        with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
            self._mock_provenance(client)
            client.return_value.request.return_value = changed
            command._dispatch()
            self.assertEqual(command.state, "failed")
            client.return_value.request.assert_called_once_with("GET", "datatables/Client%20extra")

    def test_discovered_contract_change_invalidates_open_form_and_pending_command(self):
        table = self._discover()
        submitted = self._request(table, "create")
        command = self.env["mfierp.command"].browse(submitted.action_execute()["res_id"])
        opened = self._request(table, "create")
        changed = self._metadata(True)
        self._discover(changed)
        with self.assertRaises(UserError):
            opened.action_execute()
        command.with_user(self.checker).action_approve()
        command.write({"state": "dispatching"})
        with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
            command._dispatch()
            self.assertEqual(command.state, "failed")
            client.assert_not_called()

    def test_unknown_outcome_is_never_resent_and_form_identity_is_pinned(self):
        table = self._discover()
        request = self._request(table, "delete")
        with self.assertRaises(UserError):
            request.write({"datatable_action": "create"})
        with self.assertRaises(AccessError):
            request.input_ids.filtered(lambda node: node.key == "datatable").write({"text_value": "clients"})
        command = self.env["mfierp.command"].browse(request.action_execute()["res_id"])
        command.with_user(self.checker).action_approve()
        command.write({"state": "dispatching"})
        with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
            self._mock_provenance(client)
            client.return_value.request.side_effect = [self._metadata(), FineractError("Timeout", uncertain=True)]
            command._dispatch()
            self.assertEqual(command.state, "uncertain")
            self.env["mfierp.command"]._cron_dispatch()
            self.assertEqual(client.return_value.request.call_count, 2)

    def test_unsupported_and_removed_registrations_are_blocked(self):
        metadata = self._metadata()
        metadata["columnHeaderData"][1]["columnDisplayType"] = "DATETIME"
        table = self._discover(metadata)
        self.assertFalse(table.executable)
        with self.assertRaises(UserError):
            table.with_user(self.maker).action_create_entry()
        self._discover()
        self.assertTrue(table.executable)
        with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
            client.return_value.request.return_value = []
            self.backend.with_user(self.manager).action_refresh_datatables()
        self.assertFalse(table.executable)
        with self.assertRaises(UserError):
            table.with_user(self.reader).action_read_entries()

    def test_record_context_prefills_only_the_parent_id(self):
        table = self._discover(self._metadata(True))
        client = self.env["mfierp.record"]._upsert(self.backend, "client", {"id": 8, "displayName": "Synthetic Client"})
        navigation = client.with_user(self.reader).action_datatables()
        self.assertIn(("backend_id", "=", self.backend.id), navigation["domain"])
        action = table.with_user(self.maker).with_context(**navigation["context"]).action_update_entry()
        request = self.env["mfierp.request"].with_user(self.maker).with_context(**action["context"]).create({})
        request.action_load()
        self.assertEqual(request.input_ids.filtered(lambda node: node.key == "apptableId").integer_value, 8)
        self.assertEqual(request.input_ids.filtered(lambda node: node.key == "datatableId").integer_value, 0)
        with self.assertRaises(UserError):
            wrong = self.env["mfierp.request"].with_user(self.maker).create({"datatable_id": table.id,
                "backend_id": self.backend.id, "target_id": self.loan.id})
            wrong.action_load()

    def test_product_table_writes_require_two_administrators(self):
        metadata = self._metadata()
        metadata["applicationTableName"] = "m_product_loan"
        metadata["columnHeaderData"][0]["columnName"] = "product_loan_id"
        table = self._discover(metadata)
        with self.assertRaises(AccessError):
            table.with_user(self.maker).action_create_entry()
        request = self._request(table, "create", self.manager)
        command = self.env["mfierp.command"].browse(request.action_execute()["res_id"])
        with self.assertRaises(AccessError):
            command.with_user(self.checker).action_approve()
        with self.assertRaises(AccessError):
            command.with_user(self.checker).action_reject()
        manager2 = self._make_user("mfierp_table_manager2", "group_manager")
        command.with_user(manager2).action_approve()
        self.assertEqual(command.state, "approved")
