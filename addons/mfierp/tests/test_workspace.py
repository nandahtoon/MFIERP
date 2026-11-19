# SPDX-License-Identifier: LGPL-3.0-or-later
from unittest.mock import patch
from odoo.tools import BinaryBytes
import os
import hashlib

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .test_workflows import TestMfierpWorkflows


@tagged("post_install", "-at_install")
class TestWorkspace(TestMfierpWorkflows):
    def test_retention_preserves_unknown_outcomes_and_audit_hashes(self):
        raw = b"synthetic retention evidence"
        command = self._command()
        upload = self.env["mfierp.upload"].sudo().create({"backend_id": self.backend.id,
            "command_id": command.id, "name": "synthetic.txt", "data": BinaryBytes(raw),
            "sha256": hashlib.sha256(raw).hexdigest()})
        old = fields.Datetime.subtract(fields.Datetime.now(), days=8)
        for state in ["pending", "approved", "dispatching", "uncertain", "remote_pending"]:
            command.write({"state": state, "completed_at": old})
            self.env["mfierp.upload"]._cron_purge()
            self.assertFalse(upload.purged_at)
            self.assertEqual(upload.data.content, raw)
        command.write({"state": "done", "completed_at": old})
        self.env["mfierp.upload"]._cron_purge()
        self.assertTrue(upload.purged_at)
        self.assertFalse(upload.data)
        self.assertEqual(upload.sha256, hashlib.sha256(raw).hexdigest())

    def test_source_reviewed_command_is_fixed_in_the_native_form(self):
        capability = self.env["mfierp.capability"].search([("key", "like", "__reactivate"), ("resource", "=", "clients")], limit=1)
        request = self.env["mfierp.request"].with_user(self.maker).create({"capability_id": capability.id, "backend_id": self.backend.id})
        request.action_load()
        node = request.input_ids.filtered(lambda row: row.key == "command")
        self.assertEqual(node.text_value, "reactivate")
        self.assertTrue(node.locked)
        self.assertEqual(len(request.root_input_ids), 3)
        self.assertFalse(any(request.root_input_ids.mapped("parent_id")))
        with self.assertRaises(AccessError):
            node.write({"text_value": "reject"})

    def test_revoked_maker_cannot_dispatch_an_approved_command(self):
        request = self.form(self.maker)
        request.input_ids.filtered(lambda row: row.key == "clientId").write({"integer_value": 7})
        command = self.env["mfierp.command"].browse(request.action_execute()["res_id"])
        command.with_user(self.checker).action_approve()
        self.maker.active = False
        command.write({"state": "dispatching"})
        with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
            command._dispatch()
            client.assert_not_called()
        self.assertEqual(command.state, "failed")

    def test_record_context_prefills_only_the_parent_id(self):
        capability = self.capability("GET", "/v1/loans/{loanId}/charges/{loanChargeId}")
        request = self.env["mfierp.request"].with_user(self.maker).create({"capability_id": capability.id,
            "backend_id": self.backend.id, "target_id": self.loan.id})
        request.action_load()
        self.assertEqual(request.input_ids.filtered(lambda row: row.key == "loanId").integer_value, 7)
        self.assertEqual(request.input_ids.filtered(lambda row: row.key == "loanChargeId").integer_value, 0)

    def capability(self, method, resource_path):
        from ..services import workspace
        spec = next(c for c in workspace.capabilities().values() if c["method"] == method and c["path"] == resource_path)
        return self.env["mfierp.capability"].search([("key", "=", spec["key"])], limit=1)

    def form(self, user, method="POST", path="/v1/clients/{clientId}/identifiers"):
        request = self.env["mfierp.request"].with_user(user).create({
            "capability_id": self.capability(method, path).id, "backend_id": self.backend.id})
        request.action_load()
        return request

    def test_native_nested_form_submits_immutable_review_command(self):
        request = self.form(self.maker)
        request.input_ids.filtered(lambda row: row.key == "clientId").write({"integer_value": 7})
        details = request.input_ids.filtered(lambda row: row.key == "details")
        details.child_ids.filtered(lambda row: row.key == "documentTypeId").write({"included": True, "integer_value": 3})
        details.child_ids.filtered(lambda row: row.key == "documentKey").write({"included": True, "text_value": "SYNTHETIC-ID"})
        result = request.action_execute()
        command = self.env["mfierp.command"].browse(result["res_id"])
        self.assertEqual(command.payload["body"]["documentKey"], "SYNTHETIC-ID")
        self.assertEqual(command.state, "pending")
        self.assertEqual(command.maker_id, self.maker)
        with self.assertRaises(AccessError):
            request.input_ids[0].write({"key": "arbitraryPath"})
        command.with_user(self.checker).action_approve()
        command.write({"state": "dispatching"})
        with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
            self._mock_provenance(client)
            client.return_value.request.return_value = {"resourceId": 10}
            command._dispatch()
            self.assertEqual(command.state, "done")
            self.assertEqual(client.return_value.request.call_args.args[:2], ("POST", "clients/7/identifiers"))

    def test_readers_can_read_but_cannot_open_write_workflows(self):
        with self.assertRaises(AccessError):
            self.form(self.reader)
        request = self.form(self.reader, "GET", "/v1/clients")
        with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
            client.return_value.request.return_value = {"pageItems": [{"id": 7, "displayName": "<script>bad</script>"}]}
            request.action_execute()
            self.assertNotIn("<script>", str(request.result_html))
            self.assertIn("&lt;script&gt;", str(request.result_html))

    def test_workspace_outcomes_cannot_be_fabricated(self):
        with self.assertRaises(AccessError):
            self.env["mfierp.request"].with_user(self.reader).create({"backend_id": self.backend.id,
                "capability_id": self.capability("GET", "/v1/clients").id, "result_status": "Invented balance"})

    def test_upload_bytes_are_bound_to_the_command_and_not_the_audit_payload(self):
        path = "/v1/{entityType}/{entityId}/documents"
        request = self.form(self.maker, "POST", path)
        for node in request.input_ids:
            if node.key == "entityType":
                node.write({"text_value": "clients"})
            elif node.key == "entityId":
                node.write({"integer_value": 7})
        details = request.input_ids.filtered(lambda row: row.key == "details")
        file_node = details.child_ids.filtered(lambda row: row.kind == "binary")
        self.assertEqual(len(file_node), 1)
        file_node.write({"included": True, "binary_name": "synthetic.txt", "binary_value": BinaryBytes(b"synthetic document", filename="synthetic.txt")})
        details.child_ids.filtered(lambda row: row.key == "name").write({"included": True, "text_value": "Synthetic evidence"})
        result = request.action_execute()
        command = self.env["mfierp.command"].browse(result["res_id"])
        self.assertEqual(len(command.upload_ids), 1)
        self.assertNotIn("c3ludGhldGljIGRvY3VtZW50", command.payload_preview)
        command.with_user(self.checker).action_approve()
        command.write({"state": "dispatching"})
        with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
            self._mock_provenance(client)
            client.return_value.request.return_value = {"resourceId": 101}
            command._dispatch()
            self.assertEqual(command.state, "done")
            self.assertEqual(client.return_value.request.call_args.kwargs["files"][0][1][1], b"synthetic document")
        with self.assertRaises(AccessError):
            command.upload_ids.with_user(self.maker).write({"data": BinaryBytes(b"changed")})

    def test_request_fields_do_not_cross_user_or_company_boundaries(self):
        request = self.form(self.maker, "GET", "/v1/clients")
        with self.assertRaises(AccessError):
            request.with_user(self.reader).action_execute()
        with self.assertRaises(AccessError):
            self.env["mfierp.request"].with_user(self.maker).create({"backend_id": self.other_backend.id,
                "company_id": self.other_company.id, "capability_id": self.capability("GET", "/v1/clients").id}).action_load()

    def test_password_workflow_uses_references_and_independent_administrator(self):
        request = self.form(self.manager, "POST", "/v1/users/{userId}/pwd")
        request.input_ids.filtered(lambda row: row.key == "userId").write({"integer_value": 7})
        details = request.input_ids.filtered(lambda row: row.key == "details")
        password_fields = details.child_ids.filtered(lambda row: row.kind == "secret")
        self.assertEqual(set(password_fields.mapped("key")), {"password", "repeatPassword"})
        password_fields.write({"included": True, "secret_reference": "MFIERP_WORKFLOW_SECRET_TEST_PASSWORD"})
        with patch.dict(os.environ, {"MFIERP_SECRET_BINDING_KEY": "synthetic-review-signing-key-at-least-32-characters",
                "MFIERP_WORKFLOW_SECRET_TEST_PASSWORD": "synthetic-user-password"}):
            result = request.action_execute()
            command = self.env["mfierp.command"].browse(result["res_id"])
            self.assertNotIn("synthetic-user-password", command.payload_preview)
            with self.assertRaises(AccessError):
                command.with_user(self.checker).action_approve()
            administrator = self._make_user("mfierp_second_administrator", "group_manager")
            command.with_user(administrator).action_approve()
            command.write({"state": "dispatching"})
            with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
                self._mock_provenance(client)
                client.return_value.request.return_value = {"resourceId": 7}
                command._dispatch()
                self.assertEqual(command.state, "done")
                self.assertEqual(client.return_value.request.call_args.kwargs["payload"]["password"], "synthetic-user-password")
                self.assertNotIn("synthetic-user-password", command.payload_preview)
