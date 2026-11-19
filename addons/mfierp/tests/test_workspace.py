# SPDX-License-Identifier: LGPL-3.0-or-later
from unittest.mock import patch
from odoo.tools import BinaryBytes
import os
import hashlib

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .test_workflows import TestMfierpWorkflows
from ..services.fineract import FineractError


@tagged("post_install", "-at_install")
class TestWorkspace(TestMfierpWorkflows):
    def test_collection_preview_is_projected_escaped_and_expires(self):
        capability = self.variant("/v1/collectionsheet", "generateCollectionSheet")
        request = self.env["mfierp.request"].with_user(self.maker).create({"capability_id": capability.id, "backend_id": self.backend.id})
        request.action_load()
        request.input_ids.filtered(lambda row: row.key == "officeId").write({"integer_value": 1})
        request.input_ids.filtered(lambda row: row.key == "transactionDate").write({"date_value": "2026-11-19"})
        command = self.env["mfierp.command"].browse(request.action_execute()["res_id"])
        command.with_user(self.checker).action_approve()
        command.write({"state": "dispatching"})
        with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
            self._mock_provenance(client)
            client.return_value.request.return_value = {"clients": [{"clientName": "<script>synthetic</script>", "loans": [
                {"loanId": 7, "totalDue": 12.5, "chargesDue": 0.75, "password": "not-retained"}]}]}
            command._dispatch()
        self.assertEqual(command.state, "done")
        self.assertEqual(command.preview_data["rows"][0]["due"], 12.5)
        self.assertEqual(command.preview_data["rows"][0]["charges"], 0.75)
        self.assertNotIn("not-retained", str(command.preview_data))
        self.assertNotIn("<script>", str(command.preview_html))
        with self.assertRaises(AccessError):
            command.with_user(self.reader).read(["preview_data"])
        digest = command.preview_digest
        command.write({"completed_at": fields.Datetime.subtract(fields.Datetime.now(), days=8)})
        self.env["mfierp.command"]._cron_purge_previews()
        self.assertFalse(command.preview_data)
        self.assertTrue(command.preview_purged_at)
        self.assertEqual(command.preview_digest, digest)

    def test_collection_posting_waits_for_account_reconciliation(self):
        capability = self.variant("/v1/collectionsheet", "saveCollectionSheet")
        request = self.env["mfierp.request"].with_user(self.maker).create({"capability_id": capability.id, "backend_id": self.backend.id})
        request.action_load()
        request.input_ids.filtered(lambda row: row.key in ["transactionDate", "actualDisbursementDate"]).write({"date_value": "2026-11-19"})
        repayments = request.input_ids.filtered(lambda row: row.key == "bulkRepaymentTransactions")
        repayments.action_add_item()
        repayments.child_ids.child_ids.filtered(lambda row: row.key == "loanId").write({"integer_value": 7})
        repayments.child_ids.child_ids.filtered(lambda row: row.key == "transactionAmount").write({"number_value": 12.5})
        command = self.env["mfierp.command"].browse(request.action_execute()["res_id"])
        command.with_user(self.checker).action_approve()
        command.write({"state": "dispatching"})
        with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
            self._mock_provenance(client)
            client.return_value.request.return_value = {"resourceId": 99, "commandId": 77}
            command._dispatch()
            self.assertEqual(command.state, "remote_pending")
            self.assertEqual(command.result_command_id, 77)
            with self.assertRaises(UserError):
                command._dispatch()
            self.assertEqual(client.return_value.request.call_count, 1)

    def test_malformed_references_after_sending_are_uncertain(self):
        command = self._command()
        command.with_user(self.checker).action_approve()
        command.write({"state": "dispatching"})
        with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
            self._mock_provenance(client)
            client.return_value.request.return_value = {"resourceId": "invalid-reference"}
            command._dispatch()
            self.assertEqual(command.state, "uncertain")
            self.assertFalse(command.completed_at)

    def test_attendance_uses_scoped_option_objects_and_requires_review(self):
        group = self.env["mfierp.record"]._upsert(self.backend, "group", {"id": 8, "name": "Synthetic group"})
        capability = self.variant("/v1/{entityType}/{entityId}/meetings", "recordGroupsAttendance")
        request = self.env["mfierp.request"].with_user(self.maker).create({"capability_id": capability.id,
            "backend_id": self.backend.id, "target_id": group.id})
        request.action_load()
        request.input_ids.filtered(lambda row: row.key == "calendarId").write({"integer_value": 3})
        request.input_ids.filtered(lambda row: row.key == "meetingDate").write({"date_value": "2026-11-19"})
        attendance = request.input_ids.filtered(lambda row: row.key == "clientsAttendance")
        attendance.action_add_item()
        attendance.child_ids.child_ids.filtered(lambda row: row.key == "clientId").write({"integer_value": 7})
        option = attendance.child_ids.child_ids.filtered(lambda row: row.key == "attendanceType")
        option.child_ids.filtered(lambda row: row.key == "id").write({"integer_value": 1})
        command = self.env["mfierp.command"].browse(request.action_execute()["res_id"])
        self.assertEqual(command.state, "pending")
        self.assertEqual(command.payload["body"]["clientsAttendance"], [{"clientId": 7, "attendanceType": {"id": 1}}])
        self.assertNotIn("calenderId", command.payload["query"])
    def test_calendar_context_rejects_an_unrelated_entity_kind(self):
        capability = self.variant("/v1/{entityType}/{entityId}/calendars/{calendarId}", "editGroupsMeeting")
        request = self.env["mfierp.request"].with_user(self.maker).create({"capability_id": capability.id,
            "backend_id": self.backend.id, "target_id": self.loan.id})
        with self.assertRaises(UserError):
            request.action_load()
        self.assertFalse(request.initialized)

    def test_group_membership_rows_validate_before_approval_and_dispatch(self):
        group = self.env["mfierp.record"]._upsert(self.backend, "group", {"id": 8, "name": "Synthetic group"})
        capability = self.variant("/v1/groups/{groupId}", "associateClients")
        request = self.env["mfierp.request"].with_user(self.maker).create({"capability_id": capability.id,
            "backend_id": self.backend.id, "target_id": group.id})
        request.action_load()
        self.assertEqual(request.input_ids.filtered(lambda row: row.key == "groupId").integer_value, 8)
        members = request.input_ids.filtered(lambda row: row.key == "clientMembers")
        members.action_add_item()
        members.action_add_item()
        members.child_ids.write({"integer_value": 7})
        with self.assertRaises(UserError):
            request.action_execute()
        self.assertFalse(request.command_id)
        members.child_ids[-1].write({"integer_value": 9})
        command = self.env["mfierp.command"].browse(request.action_execute()["res_id"])
        self.assertEqual(command.payload["body"], {"clientMembers": [7, 9]})
        command.with_user(self.checker).action_approve()
        command.write({"state": "dispatching"})
        with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
            self._mock_provenance(client)
            client.return_value.request.return_value = {"resourceId": 8}
            command._dispatch()
            self.assertEqual(client.return_value.request.call_args.args[:2], ("POST", "groups/8"))
            self.assertEqual(client.return_value.request.call_args.kwargs["params"], {"command": "associateClients"})
        self.assertEqual(command.state, "done")

    def test_calendar_context_keeps_parent_and_calendar_ids_separate(self):
        group = self.env["mfierp.record"]._upsert(self.backend, "group", {"id": 8, "name": "Synthetic group"})
        capability = self.variant("/v1/{entityType}/{entityId}/calendars/{calendarId}", "editGroupsMeeting")
        self.assertIn(capability, self.env["mfierp.capability"].search(group.action_workspace()["domain"]))
        request = self.env["mfierp.request"].with_user(self.maker).create({"capability_id": capability.id,
            "backend_id": self.backend.id, "target_id": group.id})
        request.action_load()
        self.assertEqual(request.input_ids.filtered(lambda row: row.key == "entityId").integer_value, 8)
        self.assertEqual(request.input_ids.filtered(lambda row: row.key == "calendarId").integer_value, 0)
        with self.assertRaises(AccessError):
            request.input_ids.filtered(lambda row: row.key == "entityType").write({"text_value": "clients"})
        request.input_ids.filtered(lambda row: row.key == "calendarId").write({"integer_value": 3})
        request.input_ids.filtered(lambda row: row.key == "startDate").write({"date_value": "2026-11-19"})
        request.input_ids.filtered(lambda row: row.key == "frequency").write({"integer_value": 2})
        request.input_ids.filtered(lambda row: row.key == "interval").write({"integer_value": 1})
        request.input_ids.filtered(lambda row: row.key == "title").write({"text_value": "Synthetic weekly meeting"})
        with self.assertRaises(UserError):
            request.action_execute()
        request.input_ids.filtered(lambda row: row.key == "repeatsOnDay").write({"included": True, "integer_value": 4})
        command = self.env["mfierp.command"].browse(request.action_execute()["res_id"])
        self.assertNotIn("command", command.payload["query"])
        command.with_user(self.checker).action_approve()
        command.write({"state": "dispatching"})
        with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
            self._mock_provenance(client)
            client.return_value.request.return_value = {"resourceId": 3}
            command._dispatch()
            self.assertEqual(client.return_value.request.call_args.args[:2], ("PUT", "groups/8/calendars/3"))
        self.assertEqual(command.state, "done")

    def test_center_calendar_list_is_contextual_reader_access(self):
        center = self.env["mfierp.record"]._upsert(self.backend, "center", {"id": 9, "name": "Synthetic center"})
        capability = self.variant("/v1/{entityType}/{entityId}/calendars", "listCentersCalendars")
        request = self.env["mfierp.request"].with_user(self.reader).create({"capability_id": capability.id,
            "backend_id": self.backend.id, "target_id": center.id})
        request.action_load()
        with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
            client.return_value.request.return_value = [{"id": 3, "title": "Synthetic meeting"}]
            request.action_execute()
            self.assertEqual(client.return_value.request.call_args.args[:2], ("GET", "centers/9/calendars"))
        self.assertFalse(request.command_id)

    def test_form_contract_is_pinned_when_loaded_and_cannot_be_rebound(self):
        request = self.form(self.reader, "GET", "/v1/clients")
        self.assertTrue(request.contract_digest)
        with self.assertRaises(AccessError):
            request.write({"contract_digest": "forged"})
        with patch("odoo.addons.mfierp.wizard.mfierp_request.workspace.contract_digest", return_value="changed"):
            with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
                with self.assertRaises(UserError):
                    request.action_execute()
                client.assert_not_called()

    def test_deposit_timeout_is_reserved_once_and_never_replayed(self):
        capability = self.variant("/v1/recurringdepositaccounts/{recurringDepositAccountId}/transactions", "deposit")
        request = self.env["mfierp.request"].with_user(self.maker).create({"capability_id": capability.id, "backend_id": self.backend.id})
        request.action_load()
        request.input_ids.filtered(lambda row: row.key == "recurringDepositAccountId").write({"integer_value": 12})
        request.input_ids.filtered(lambda row: row.key == "transactionDate").write({"date_value": "2026-11-19"})
        request.input_ids.filtered(lambda row: row.key == "transactionAmount").write({"number_value": 2.75})
        request.input_ids.filtered(lambda row: row.key == "paymentTypeId").write({"integer_value": 3})
        command = self.env["mfierp.command"].browse(request.action_execute()["res_id"])
        self.assertEqual(command.payload["body"]["transactionAmount"], 2.75)
        command.with_user(self.checker).action_approve()
        command.write({"state": "dispatching"})
        with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
            self._mock_provenance(client)
            client.return_value.request.side_effect = FineractError("Synthetic timeout", uncertain=True)
            command._dispatch()
            self.assertEqual(command.state, "uncertain")
            with self.assertRaises(UserError):
                command._dispatch()
            self.assertEqual(client.return_value.request.call_count, 1)
            self.assertEqual(client.return_value.request.call_args.args[:2], ("POST", "recurringdepositaccounts/12/transactions"))

    def test_deposit_undo_constant_cannot_be_changed_through_rpc(self):
        capability = self.variant("/v1/fixeddepositaccounts/{fixedDepositAccountId}/transactions/{transactionId}", "undo")
        request = self.env["mfierp.request"].with_user(self.maker).create({"capability_id": capability.id, "backend_id": self.backend.id})
        request.action_load()
        amount = request.input_ids.filtered(lambda row: row.key == "transactionAmount")
        self.assertEqual(amount.number_value, 0)
        self.assertTrue(amount.locked)
        with self.assertRaises(AccessError):
            amount.write({"number_value": 100})

    def test_reader_can_read_deposit_closure_template_without_a_command(self):
        capability = self.variant("/v1/fixeddepositaccounts/{accountId}/template", "close")
        request = self.env["mfierp.request"].with_user(self.reader).create({"capability_id": capability.id, "backend_id": self.backend.id})
        request.action_load()
        request.input_ids.filtered(lambda row: row.key == "accountId").write({"integer_value": 12})
        with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
            client.return_value.request.return_value = {"id": 12, "maturityAmount": 102.75}
            request.action_execute()
            self.assertEqual(client.return_value.request.call_args.args[:2], ("GET", "fixeddepositaccounts/12/template"))
            self.assertEqual(client.return_value.request.call_args.kwargs["params"], {"command": "close"})
        self.assertFalse(request.command_id)

    def variant(self, path, command):
        from ..services import workspace
        spec = next(c for c in workspace.capabilities().values() if c["path"] == path
            and (c.get("source_form") or c.get("source_service")) and c["key"].endswith("__" + command))
        return self.env["mfierp.capability"].search([("key", "=", spec["key"])], limit=1)

    def test_reschedule_from_loan_context_queues_one_independent_command(self):
        capability = self.variant("/v1/rescheduleloans", "reschedule")
        self.assertIn(capability, self.env["mfierp.capability"].search(self.loan.action_workspace()["domain"]))
        request = self.env["mfierp.request"].with_user(self.maker).create({"capability_id": capability.id,
            "backend_id": self.backend.id, "target_id": self.loan.id})
        request.action_load()
        loan_field = request.input_ids.filtered(lambda row: row.key == "loanId")
        self.assertEqual(loan_field.integer_value, 7)
        for key in ["rescheduleFromDate", "submittedOnDate"]:
            request.input_ids.filtered(lambda row, key=key: row.key == key).write({"date_value": "2026-11-19"})
        request.input_ids.filtered(lambda row: row.key == "rescheduleReasonId").write({"integer_value": 3})
        command = self.env["mfierp.command"].browse(request.action_execute()["res_id"])
        self.assertEqual(command.payload["body"]["loanId"], 7)
        self.assertEqual(command.state, "pending")
        command.with_user(self.checker).action_approve()
        command.write({"state": "dispatching"})
        with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
            self._mock_provenance(client)
            client.return_value.request.return_value = {"resourceId": 44}
            command._dispatch()
            self.assertEqual(client.return_value.request.call_count, 1)
            self.assertEqual(client.return_value.request.call_args.args[:2], ("POST", "rescheduleloans"))
            self.assertEqual(client.return_value.request.call_args.kwargs["params"], {"command": "reschedule"})
        self.assertEqual(command.state, "done")

    def test_reschedule_list_uses_loan_context_and_readers_can_view_pending(self):
        capability = self.env["mfierp.capability"].search([("name", "=", "Loan rescheduling: list requests")], limit=1)
        request = self.env["mfierp.request"].with_user(self.reader).create({"capability_id": capability.id,
            "backend_id": self.backend.id, "target_id": self.loan.id})
        request.action_load()
        self.assertTrue(request.input_ids.filtered(lambda row: row.key == "loanId").included)
        self.assertEqual(request._envelope()["query"], {"loanId": 7})
        pending = self.variant("/v1/rescheduleloans", "pending")
        pending.with_user(self.reader)._assert_role()
        with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
            client.return_value.request.return_value = [{"id": 44, "loanId": 7}]
            request.action_execute()
        self.assertFalse(request.command_id)

    def test_provisioning_requires_manager_and_distinct_manager_review(self):
        capability = self.variant("/v1/provisioningentries/{entryId}", "createjournalentry")
        with self.assertRaises(AccessError):
            capability.with_user(self.maker).action_open()
        request = self.env["mfierp.request"].with_user(self.manager).create({"capability_id": capability.id,
            "backend_id": self.backend.id})
        request.action_load()
        request.input_ids.filtered(lambda row: row.key == "entryId").write({"integer_value": 5})
        command = self.env["mfierp.command"].browse(request.action_execute()["res_id"])
        with self.assertRaises(AccessError):
            command.with_user(self.checker).action_approve()
        reviewer = self._make_user("mfierp_provisioning_checker", "group_manager")
        command.with_user(reviewer).action_approve()
        self.assertEqual(command.payload["body"], {})
        self.assertEqual(command.state, "approved")

    def test_source_reviewed_no_body_action_requires_independent_administrator(self):
        capability = self.variant("/v1/surveys/{id}", "activate")
        request = self.env["mfierp.request"].with_user(self.manager).create({"capability_id": capability.id,
            "backend_id": self.backend.id})
        request.action_load()
        self.assertEqual(len(request.root_input_ids), 2)
        request.input_ids.filtered(lambda row: row.key == "id").write({"integer_value": 7})
        command = self.env["mfierp.command"].browse(request.action_execute()["res_id"])
        with self.assertRaises(AccessError):
            command.with_user(self.checker).action_approve()
        administrator = self._make_user("mfierp_survey_checker", "group_manager")
        command.with_user(administrator).action_approve()
        command.write({"state": "dispatching"})
        with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
            self._mock_provenance(client)
            client.return_value.request.return_value = {}
            command._dispatch()
            self.assertIsNone(client.return_value.request.call_args.kwargs["payload"])
            self.assertEqual(command.state, "remote_pending")

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
        capability = self.variant("/v1/clients/{clientId}", "reactivate")
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
