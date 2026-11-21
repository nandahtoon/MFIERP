"""Lifecycle safety gates and fail-closed orchestration, without Odoo or a database."""
import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock


spec = importlib.util.spec_from_file_location(
    "core_lifecycle", Path(__file__).resolve().parents[1] / "scripts/verify_core_lifecycle.py")
lifecycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lifecycle)


class CoreLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.before = {"core_state": "installed", "source_version": "20.0.10.0.0",
            "installed_version": "20.0.10.0.0", "pending_modules": [], "downstream_modules": [],
            "optional_models": [], "mfierp_attachments": 0, "installed_modules": {
                name: {"version": "20.0.1.0", "license": "LGPL-3"} for name in ("base", "web", "mfierp")},
            "model_counts": {name: 0 for name in lifecycle.REQUIRED_MODELS | {"mfierp.request", "mfierp.upload"}},
            "base_references": {"base.user_root": ("res.users", 1)}}
        self.before["model_counts"]["mfierp.capability"] = 1097
        self.after = {"core_state": "uninstalled", "installed_modules": {
            name: info for name, info in self.before["installed_modules"].items() if name != "mfierp"},
            "base_references": copy.deepcopy(self.before["base_references"]), "pending_modules": [],
            "registered_models": [], "model_metadata": 0, "field_metadata": 0, "module_xmlids": 0,
            "retained_owned_records": {}, "retained_tables": [], "optional_models": [], "mfierp_attachments": 0}

    def assert_refused_before_uninstall(self, before):
        uninstall, inspect_after = Mock(), Mock(return_value=self.after)
        with self.assertRaises(lifecycle.LifecycleCheckError):
            lifecycle.perform_uninstall(before, uninstall, inspect_after)
        uninstall.assert_not_called()
        inspect_after.assert_not_called()

    def test_database_opt_in_is_exact_and_narrow(self):
        for database in ("mfierp_test", "mfierp_test_wp01_final_clean", "mfierp_test_" + "a" * 51):
            lifecycle.check_guard(database, database, lifecycle.OPT_IN, 20, True)
        for database in (None, "", "mfierp", "mfierp_demo", "mfierp_testish", "MFIERP_TEST",
                "mfierp_test_", "mfierp_test_../x", "mfierp_test_;drop", "mfierp_test_" + "a" * 52):
            with self.subTest(database=database), self.assertRaises(lifecycle.LifecycleCheckError):
                lifecycle.check_guard(database, database, lifecycle.OPT_IN, 20, True)
        for requested, token, version, superuser in (("mfierp_test_other", lifecycle.OPT_IN, 20, True),
                ("mfierp_test", "", 20, True), ("mfierp_test", True, 20, True),
                ("mfierp_test", lifecycle.OPT_IN, 19, True), ("mfierp_test", lifecycle.OPT_IN, True, True),
                ("mfierp_test", lifecycle.OPT_IN, 20, False), ("mfierp_test", lifecycle.OPT_IN, 20, 1)):
            with self.subTest(requested=requested, version=version), self.assertRaises(lifecycle.LifecycleCheckError):
                lifecycle.check_guard("mfierp_test", requested, token, version, superuser)

    def test_manifest_rejects_optional_or_missing_core_dependencies(self):
        manifest = {"depends": ["base", "web"], "license": "LGPL-3", "installable": True, "version": "20.0.10.0.0"}
        self.assertEqual(lifecycle.check_manifest(manifest), "20.0.10.0.0")
        for dependencies in (["base"], ["base", "web", "crm"], ["base", "account"], ["base", "base"],
                ["web", "web_enterprise"], "base,web", ["base", 1]):
            with self.subTest(dependencies=dependencies), self.assertRaises(lifecycle.LifecycleCheckError):
                lifecycle.check_manifest(dict(manifest, depends=dependencies))

    def test_business_and_transient_rows_refuse_without_clearing_them(self):
        for model in ("mfierp.backend", "mfierp.command", "mfierp.record", "mfierp.upload", "mfierp.request"):
            before = copy.deepcopy(self.before)
            before["model_counts"][model] = 1
            self.assert_refused_before_uninstall(before)
            self.assertEqual(before["model_counts"][model], 1)

    def test_version_drift_pending_operations_and_dependents_block_uninstall(self):
        for change in ({"core_state": "uninstalled"}, {"installed_version": "20.0.9.0.0"},
                {"source_version": ""}, {"pending_modules": ["unrelated_module"]},
                {"downstream_modules": ["customer_addon"]}):
            self.assert_refused_before_uninstall(dict(self.before, **change))

    def test_orphan_attachment_refuses_uninstall_even_without_model_rows(self):
        self.assert_refused_before_uninstall(dict(self.before, mfierp_attachments=1))

    def test_crm_account_or_enterprise_cannot_be_claimed_as_absent(self):
        for module in ("crm", "account", "web_enterprise", "mfierp_crm", "mfierp_future_adapter"):
            before = copy.deepcopy(self.before)
            before["installed_modules"][module] = {"version": "20.0.1.0", "license": "LGPL-3"}
            self.assert_refused_before_uninstall(before)
        for license_name in ("OEEL-1", "OPL-1", "Other proprietary"):
            before = copy.deepcopy(self.before)
            before["installed_modules"]["unknown_licensed_extension"] = {"version": "1", "license": license_name}
            self.assert_refused_before_uninstall(before)
        self.assert_refused_before_uninstall(dict(self.before, optional_models=["account.move"]))

    def test_missing_catalog_or_model_baseline_blocks_uninstall(self):
        before = copy.deepcopy(self.before)
        before["model_counts"]["mfierp.capability"] = 0
        self.assert_refused_before_uninstall(before)
        del before["model_counts"]["mfierp.command"]
        self.assert_refused_before_uninstall(before)

    def test_success_uses_one_uninstall_and_a_post_uninstall_inspection(self):
        calls = []
        def uninstall():
            calls.append("uninstall")
        def inspect_after():
            calls.append("fresh-registry-inspection")
            return self.after
        self.assertEqual(lifecycle.perform_uninstall(self.before, uninstall, inspect_after), self.after)
        self.assertEqual(calls, ["uninstall", "fresh-registry-inspection"])

    def test_unknown_uninstall_failure_is_not_retried(self):
        uninstall = Mock(side_effect=RuntimeError("synthetic failure after standard module call"))
        inspect_after = Mock(return_value=self.after)
        with self.assertRaises(RuntimeError):
            lifecycle.perform_uninstall(self.before, uninstall, inspect_after)
        uninstall.assert_called_once_with()
        inspect_after.assert_not_called()

    def test_leftovers_or_changed_standard_modules_fail_after_single_uninstall(self):
        for key, value in (("registered_models", ["mfierp.command"]), ("model_metadata", 1),
                ("field_metadata", 1), ("module_xmlids", 1), ("retained_tables", ["mfierp_command"]),
                ("retained_owned_records", {"ir.access": [42]}), ("pending_modules", ["base"]),
                ("mfierp_attachments", 1),
                ("optional_models", ["crm.lead"]), ("core_state", "installed"),
                ("base_references", {}), ("installed_modules", {})):
            uninstall = Mock()
            with self.subTest(key=key), self.assertRaises(lifecycle.LifecycleCheckError):
                lifecycle.perform_uninstall(self.before, uninstall,
                    lambda item=key, evidence=value: dict(self.after, **{item: evidence}))
            uninstall.assert_called_once_with()

    def test_ordinary_python_cannot_operate_on_a_database(self):
        with self.assertRaisesRegex(lifecycle.LifecycleCheckError, "Odoo 20 shell"):
            lifecycle.run(None)


if __name__ == "__main__":
    unittest.main()
