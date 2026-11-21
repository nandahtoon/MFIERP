# SPDX-License-Identifier: LGPL-3.0-or-later
from pathlib import Path
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.modules.migration import exec_script
from odoo.tests import TransactionCase, tagged

from ..services.fineract import FineractError


@tagged("post_install", "-at_install")
class TestMfierpWorkflows(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.other_company = cls.env["res.company"].create({"name": "MFIERP Isolation Test"})
        cls.backend = cls.env["mfierp.backend"].create({"name": "Test Fineract", "company_id": cls.company.id,
            "base_url": "https://fineract.example/fineract-provider/api/v1", "tenant": "default",
            "mutation_enabled": True, "expected_version": "TEST", "expected_commit": "a" * 40})
        cls.other_backend = cls.env["mfierp.backend"].create({"name": "Other Company", "company_id": cls.other_company.id,
            "base_url": "https://other.example/fineract-provider/api/v1", "tenant": "default"})
        cls.reader = cls._make_user("mfierp_reader", "group_reader")
        cls.maker = cls._make_user("mfierp_maker", "group_operator")
        cls.checker = cls._make_user("mfierp_checker", "group_checker")
        cls.manager = cls._make_user("mfierp_manager", "group_manager")
        cls.loan = cls.env["mfierp.record"]._upsert(cls.backend, "loan", {
            "id": 7, "accountNo": "LN-7", "status": {"value": "Active"}, "currency": {"code": "USD"}})
        cls.payload = {"transactionDate": "2026-11-18", "transactionAmount": 10,
            "dateFormat": "yyyy-MM-dd", "locale": "en"}

    @classmethod
    def _make_user(cls, login, group):
        return cls.env["res.users"].create({"name": login, "login": login,
            "company_id": cls.company.id, "company_ids": [Command.set(cls.company.ids)],
            "group_ids": [Command.set([cls.env.ref("mfierp." + group).id])]})

    def _command(self):
        return self.env["mfierp.command"].with_user(self.maker)._enqueue(self.backend.with_user(self.maker),
            "repay_loan", self.payload, self.loan.with_user(self.maker))

    def _mock_provenance(self, client):
        client.return_value.info.return_value = {"git": {"build": {"version": "TEST"}, "commit": {"id": {"full": "a" * 40}}, "dirty": "false"}}

    def test_maker_checker_and_immutable_payload(self):
        command = self._command()
        with self.assertRaises(AccessError):
            command.with_user(self.maker).write({"payload": dict(self.payload, transactionAmount=999)})
        with self.assertRaises(AccessError):
            command.with_user(self.maker).action_approve()
        command.with_user(self.checker).action_approve()
        self.assertEqual(command.state, "approved")
        self.assertEqual(command.checker_id, self.checker)
        with self.assertRaises(UserError):
            command.with_user(self.checker).action_approve()
        with self.assertRaises(AccessError):
            command.sudo().unlink()

    def test_manager_cannot_approve_own_command(self):
        command = self.env["mfierp.command"].with_user(self.manager)._enqueue(self.backend.with_user(self.manager),
            "repay_loan", self.payload, self.loan.with_user(self.manager))
        with self.assertRaises(UserError):
            command.with_user(self.manager).action_approve()

    def test_company_isolation_applies_to_actions_and_search(self):
        hidden = self.env["mfierp.record"]._upsert(self.other_backend, "client", {"id": 1, "displayName": "Hidden"})
        self.assertFalse(self.env["mfierp.record"].with_user(self.reader).search([("id", "=", hidden.id)]))
        with self.assertRaises(AccessError):
            hidden.with_user(self.reader).action_refresh()
        with self.assertRaises(AccessError):
            self.other_backend.with_user(self.manager).action_sync()

    def test_reader_cannot_submit_or_mutate_snapshot(self):
        with self.assertRaises(AccessError):
            self.env["mfierp.command"].with_user(self.reader)._enqueue(self.backend.with_user(self.reader), "repay_loan", self.payload, self.loan)
        with self.assertRaises(AccessError):
            self.loan.with_user(self.maker).write({"balance": 9999})
        with self.assertRaises(AccessError):
            self.loan.with_user(self.reader).action_operation()

    def test_cross_connection_target_rejected(self):
        wrong = self.env["mfierp.record"]._upsert(self.other_backend, "loan", {"id": 8, "accountNo": "OTHER"})
        with self.assertRaises((AccessError, UserError)):
            self.env["mfierp.command"].with_user(self.maker)._enqueue(self.backend.with_user(self.maker),
                "repay_loan", self.payload, wrong.with_user(self.maker))

    def test_successful_dispatch_and_remote_pending(self):
        for response in [{"resourceId": 11, "commandId": 100}, {"resourceId": 11}, {"commandId": 101}]:
            command = self._command()
            command.with_user(self.checker).action_approve()
            command.write({"state": "dispatching"})
            with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
                self._mock_provenance(client)
                client.return_value.request.return_value = response
                command._dispatch()
                self.assertEqual(command.state, "remote_pending")
                self.assertTrue(command.response_received_at)
                self.assertFalse(command.completed_at)
                self.assertEqual(command.result_resource_id, response.get("resourceId", 0))
                self.assertEqual(command.result_command_id, response.get("commandId", 0))
                self.assertEqual(client.return_value.request.call_count, 1)
                self.assertEqual(client.return_value.request.call_args.kwargs["idempotency_key"], command.idempotency_key)
                with self.assertRaises(UserError):
                    command._dispatch()
                self.assertEqual(client.return_value.request.call_count, 1)

    def test_timeout_never_replayed(self):
        command = self._command()
        command.with_user(self.checker).action_approve()
        command.write({"state": "dispatching"})
        with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
            self._mock_provenance(client)
            client.return_value.request.side_effect = FineractError("Timeout", uncertain=True)
            command._dispatch()
            self.assertEqual(command.state, "uncertain")
            self.assertFalse(command.response_received_at)
            with self.assertRaises(UserError):
                command._dispatch()
            self.assertEqual(client.return_value.request.call_count, 1)

    def test_dispatch_rechecks_reservation_under_reconciliation_lock(self):
        command = self._command()
        command.with_user(self.checker).action_approve()
        command.write({"state": "dispatching"})
        command_class = type(command)
        original_lock = command_class._lock

        def reconciled_before_lock(record):
            # Model a reconciler winning the gap after the durable reservation.
            # A cached dispatching state must not authorize a later HTTP write.
            record.write({"state": "failed", "resolution_note": "Independently confirmed not applied."})
            original_lock(record)

        with patch.object(command_class, "_lock", side_effect=reconciled_before_lock, autospec=True) as lock, patch(
                "odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
            with self.assertRaises(UserError):
                command._dispatch()
            lock.assert_called_once_with(command)
            client.assert_not_called()
    def test_cron_reserves_before_network_and_does_not_select_uncertain(self):
        command = self._command()
        command.with_user(self.checker).action_approve()
        barriers = []

        def progress(*args, **kwargs):
            barriers.append(command.state)
            return 60

        def remote(*args, **kwargs):
            self.assertEqual(barriers, ["dispatching"])
            raise FineractError("Timeout", uncertain=True)

        cron_class = type(self.env["ir.cron"])
        with patch.object(cron_class, "_commit_progress", side_effect=progress), patch(
                "odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
            self._mock_provenance(client)
            client.return_value.request.side_effect = remote
            self.env["mfierp.command"]._cron_dispatch()
            self.assertEqual(command.state, "uncertain")
            self.env["mfierp.command"]._cron_dispatch()
            self.assertEqual(client.return_value.request.call_count, 1)

    def test_report_output_escapes_remote_html(self):
        report = self.env["mfierp.record"]._upsert(self.backend, "report", {"id": 1, "reportName": "Client Summary", "reportType": "Table"})
        wizard = self.env["mfierp.report"].with_user(self.reader).create({"backend_id": self.backend.id, "report_id": report.id})
        with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
            client.return_value.request.return_value = {"columnHeaders": [{"columnName": "Client"}], "data": [{"row": ["<script>alert(1)</script>"]}]}
            wizard.action_run()
            self.assertNotIn("<script>", str(wizard.result_html))
            self.assertIn("&lt;script&gt;", str(wizard.result_html))

    def test_sync_upsert_and_detail_lines(self):
        self.env["mfierp.record"]._upsert(self.backend, "loan", {"id": 7, "accountNo": "LN-7", "summary": {"totalOutstanding": 25}})
        self.assertEqual(self.loan.outstanding, 25)
        self.assertEqual(self.env["mfierp.record"].search_count([("backend_id", "=", self.backend.id), ("kind", "=", "loan"), ("remote_id", "=", 7)]), 1)
        self.loan._replace_lines({"repaymentSchedule": {"periods": [{"period": 1, "dueDate": [2026, 12, 1], "totalDueForPeriod": 12.5}]},
            "transactions": [{"id": 99, "type": {"value": "Repayment"}, "date": [2026, 11, 18], "amount": 10}]})
        self.assertEqual(len(self.loan.line_ids), 2)
        self.assertEqual(set(self.loan.line_ids.mapped("kind")), {"schedule", "transaction"})

    def test_snapshot_projection_drops_unneeded_identity_fields(self):
        record = self.env["mfierp.record"]._upsert(self.backend, "client", {
            "id": 88, "displayName": "Synthetic Client", "identityDocuments": [{"secret": "not needed"}],
            "unneededPrivateAttribute": "not copied"})
        self.assertNotIn("identityDocuments", record.raw_data)
        self.assertNotIn("unneededPrivateAttribute", record.raw_data)

    def test_dispatch_fails_closed_when_runtime_pin_drifts(self):
        command = self._command()
        command.with_user(self.checker).action_approve()
        command.write({"state": "dispatching"})
        with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
            self._mock_provenance(client)
            client.return_value.info.return_value["git"]["build"]["version"] = "UNREVIEWED"
            command._dispatch()
            self.assertEqual(command.state, "failed")
            client.return_value.request.assert_not_called()

    def test_dispatch_blocks_dirty_or_missing_build_attestation(self):
        for dirty in ("true", None):
            command = self._command()
            command.with_user(self.checker).action_approve()
            command.write({"state": "dispatching"})
            with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
                self._mock_provenance(client)
                if dirty is None:
                    client.return_value.info.return_value["git"].pop("dirty")
                else:
                    client.return_value.info.return_value["git"]["dirty"] = dirty
                command._dispatch()
                self.assertEqual(command.state, "failed")
                client.return_value.request.assert_not_called()

    def test_disabled_connection_never_sends_post(self):
        command = self._command()
        command.with_user(self.checker).action_approve()
        command.write({"state": "dispatching"})
        self.backend.mutation_enabled = False
        with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
            command._dispatch()
            self.assertEqual(command.state, "failed")
            client.assert_not_called()

    def test_native_wizard_creates_reviewable_command(self):
        office = self.env["mfierp.record"]._upsert(self.backend, "office", {"id": 1, "name": "Head Office"})
        wizard = self.env["mfierp.operation"].with_user(self.maker).create({"backend_id": self.backend.id,
            "operation": "create_client", "office_id": office.id, "firstname": "Test", "lastname": "Client"})
        result = wizard.action_submit()
        self.assertEqual(result["id"], self.env.ref("mfierp.mfierp_command_action").id)
        command = self.env["mfierp.command"].browse(result["res_id"])
        self.assertEqual(command.maker_id, self.maker)
        self.assertEqual(command.payload["officeId"], 1)
        self.assertFalse(command.payload["active"])
        self.assertEqual(command.payload["externalId"], "MFIERP-" + command.idempotency_key)
        self.assertEqual(command.state, "pending")

    def test_operation_company_exists_before_connection_selection(self):
        wizard = self.env["mfierp.operation"].with_user(self.maker).new({})
        self.assertEqual(wizard.company_id, self.company)
        self.assertFalse(wizard.backend_id)

    def test_reconciliation_requires_evidence(self):
        command = self._command()
        command.write({"state": "uncertain"})
        wizard = self.env["mfierp.reconcile"].with_user(self.manager).create({"command_id": command.id,
            "outcome": "done", "resource_id": 10, "note": "short"})
        with self.assertRaises(UserError):
            wizard.action_record()
        wizard.note = "Verified Fineract audit entry 100 and transaction 10 by independent review."
        wizard.resource_id = 0
        with self.assertRaises(UserError):
            wizard.with_context(reconciliation_without_resource=True).action_record()
        wizard.resource_id = 10
        with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
            with self.assertRaisesRegex(UserError, "authoritative readback verifier"):
                wizard.with_context(authoritative_verified=True, reconciliation_without_resource=True).action_record()
            client.assert_not_called()
        self.assertEqual(command.state, "uncertain")
        self.assertFalse(command.completed_at)
        wizard.outcome = "failed"
        wizard.action_record()
        self.assertEqual(command.state, "failed")
        self.assertEqual(command.resolved_by_id, self.manager)
        self.assertTrue(command.completed_at)

    def test_reconciliation_preserves_response_and_investigation_references(self):
        for investigation_id in (0, 99):
            command = self._command()
            command.write({"state": "remote_pending", "result_resource_id": 42,
                "result_command_id": 100, "result_subresource_id": 7,
                "response_received_at": fields.Datetime.now()})
            received_at = command.response_received_at
            wizard = self.env["mfierp.reconcile"].with_user(self.manager).create({
                "command_id": command.id, "outcome": "failed", "resource_id": investigation_id,
                "note": "Independent synthetic investigation found no applied transaction; preserve received references."})
            wizard.action_record()
            self.assertEqual(command.state, "failed")
            self.assertEqual(command.result_resource_id, 42)
            self.assertEqual(command.result_command_id, 100)
            self.assertEqual(command.result_subresource_id, 7)
            self.assertEqual(command.response_received_at, received_at)
            self.assertEqual(command.reconciled_resource_id, investigation_id)

    def test_maker_manager_cannot_reconcile_either_outcome(self):
        command = self.env["mfierp.command"].with_user(self.manager)._enqueue(self.backend.with_user(self.manager),
            "repay_loan", self.payload, self.loan.with_user(self.manager))
        command.write({"state": "uncertain"})
        for outcome in ["done", "failed"]:
            wizard = self.env["mfierp.reconcile"].with_user(self.manager).create({"command_id": command.id,
                "outcome": outcome, "resource_id": 10,
                "note": "Synthetic independently investigated transaction and remote audit evidence."})
            with self.assertRaises(AccessError):
                wizard.action_record()
            self.assertEqual(command.state, "uncertain")
            self.assertFalse(command.resolved_by_id)

    def test_outcome_migration_preserves_history_without_replay(self):
        old_completed = fields.Datetime.subtract(fields.Datetime.now(), days=2)
        command = self._command()
        command.with_user(self.checker).action_approve()
        command.write({"state": "done", "completed_at": old_completed, "result_resource_id": 10,
            "result_command_id": 99, "status_message": "Old response-based confirmation",
            "resolution_note": "Historical independently supplied audit note", "resolved_by_id": self.manager.id})
        preview = self._command()
        preview.write({"state": "done", "completed_at": old_completed, "preview_digest": "a" * 64,
            "status_message": "Non-posting collection preview received"})
        pending = self._command()
        old_pending = self._command()
        old_pending.write({"state": "remote_pending", "completed_at": old_completed,
            "result_resource_id": 42, "result_command_id": 100,
            "status_message": "Old pending response timestamp"})
        new_pending = self._command()
        new_pending.write({"state": "remote_pending"})
        migrated_at = False
        migration = Path(__file__).parents[1] / "migrations" / "20.0.10.0.0" / "post-outcome-verification.py"
        before = command.read(["payload", "payload_digest", "idempotency_key", "maker_id", "checker_id",
            "approved_at", "result_resource_id", "result_command_id", "resolution_note", "resolved_by_id"])
        pending_before = old_pending.read(list(before[0].keys()))
        for _index in range(2):
            exec_script(self.env.cr, "20.0.9.0.0", str(migration), "mfierp", "post", "20.0.10.0.0")
            command.invalidate_recordset()
            self.assertEqual(command.state, "remote_pending")
            self.assertFalse(command.completed_at)
            self.assertFalse(command.response_received_at)
            self.assertEqual(command.legacy_state, "done")
            self.assertEqual(command.legacy_completed_at, old_completed)
            self.assertEqual(command.legacy_status_message, "Old response-based confirmation")
            self.assertTrue(command.legacy_reclassified_at)
            if migrated_at:
                self.assertEqual(command.legacy_reclassified_at, migrated_at)
            migrated_at = command.legacy_reclassified_at
            self.assertEqual(command.read(list(before[0].keys())), before)
            self.assertEqual(preview.state, "done")
            self.assertEqual(preview.completed_at, old_completed)
            self.assertFalse(preview.legacy_reclassified_at)
            self.assertEqual(pending.state, "pending")
            self.assertFalse(pending.legacy_reclassified_at)
            old_pending.invalidate_recordset()
            self.assertEqual(old_pending.state, "remote_pending")
            self.assertFalse(old_pending.completed_at)
            self.assertFalse(old_pending.response_received_at)
            self.assertEqual(old_pending.legacy_state, "remote_pending")
            self.assertEqual(old_pending.legacy_completed_at, old_completed)
            self.assertEqual(old_pending.legacy_status_message, "Old pending response timestamp")
            self.assertEqual(old_pending.read(list(pending_before[0].keys())), pending_before)
            self.assertTrue(old_pending.legacy_reclassified_at)
            self.assertEqual(new_pending.state, "remote_pending")
            self.assertFalse(new_pending.completed_at)
            self.assertFalse(new_pending.legacy_reclassified_at)
            with self.assertRaises(UserError):
                command._dispatch()
        with patch("odoo.addons.mfierp.models.mfierp_backend.MfierpBackend._client") as client:
            self.env["mfierp.command"]._cron_dispatch()
            client.assert_not_called()
        self.assertEqual(command.legacy_reclassified_at, migrated_at)
