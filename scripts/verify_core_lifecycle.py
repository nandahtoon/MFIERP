# SPDX-License-Identifier: LGPL-3.0-or-later
"""Verify optional-app absence and uninstall an EMPTY isolated CE test core.

Run through Odoo 20 ``odoo shell`` after clean install/upgrade tests, with this
file supplied on stdin. Required environment variables bind explicit opt-in to
the exact database. This harness never creates/drops a database, deletes audit
rows, changes credentials or calls Fineract. It refuses any tenant/form data.

MFIERP_TEST_CORE_LIFECYCLE=UNINSTALL_SYNTHETIC_ONLY
MFIERP_TEST_CORE_LIFECYCLE_DB=mfierp_test

Odoo's standard button_immediate_uninstall commits/reloads its registry; ordinary
TransactionalCase tests cannot safely perform module operations. A fresh cursor
and registry verify the committed outcome. This is CE core lifecycle evidence,
not licensed EE, optional-adapter or financial acceptance.
"""
import ast
from collections import defaultdict
import json
import os
from pathlib import Path
import re


OPT_IN = "UNINSTALL_SYNTHETIC_ONLY"
CORE_DEPENDENCIES = frozenset({"base", "web"})
OPTIONAL_MODULES = frozenset({"crm", "account", "account_accountant", "web_enterprise",
    "mfierp_crm", "mfierp_account", "mfierp_account_enterprise"})
OPTIONAL_MODELS = frozenset({"crm.lead", "account.account", "account.move"})
REQUIRED_MODELS = frozenset({"mfierp.backend", "mfierp.record", "mfierp.command", "mfierp.capability"})
STATIC_MODELS = frozenset({"mfierp.capability"})
PROPRIETARY_LICENSES = frozenset({"OEEL-1", "OPL-1", "Other proprietary"})
BASE_REFERENCES = ("base.user_root", "base.main_company", "base.group_user")


class LifecycleCheckError(RuntimeError):
    """An unmet safety gate or lifecycle postcondition; no automatic retry."""


def check_guard(database, requested_database, opt_in, major_version, is_superuser):
    if (not isinstance(database, str)
            or not re.fullmatch(r"mfierp_test(?:_[a-z0-9][a-z0-9_]{0,50})?", database)):
        raise LifecycleCheckError("Only an explicitly named mfierp_test[_suffix] database is allowed.")
    if requested_database != database or opt_in != OPT_IN:
        raise LifecycleCheckError("Explicit synthetic-only opt-in must name the exact test database.")
    if type(major_version) is not int or major_version != 20 or is_superuser is not True:
        raise LifecycleCheckError("This test requires Odoo 20's superuser shell.")


def check_manifest(manifest):
    dependencies = manifest.get("depends")
    if (not isinstance(dependencies, list) or not all(isinstance(value, str) for value in dependencies)
            or len(dependencies) != 2 or set(dependencies) != CORE_DEPENDENCIES):
        raise LifecycleCheckError("Core dependencies must be exactly base and web; optional apps stay separate.")
    if manifest.get("license") != "LGPL-3" or not manifest.get("installable"):
        raise LifecycleCheckError("The reviewed LGPL-3 core must be installable.")
    return manifest.get("version")


def check_preflight(snapshot):
    """Validate collected facts before the standard uninstall can be invoked."""
    if snapshot.get("core_state") != "installed":
        raise LifecycleCheckError("The core must be installed before this lifecycle check.")
    if not snapshot.get("source_version") or snapshot.get("installed_version") != snapshot["source_version"]:
        raise LifecycleCheckError("Run the core upgrade first; installed and source versions must match.")
    if snapshot.get("pending_modules") or snapshot.get("downstream_modules"):
        raise LifecycleCheckError("Queued module operations or installed dependents block this isolated test.")
    installed = snapshot.get("installed_modules", {})
    if not CORE_DEPENDENCIES <= installed.keys() or "mfierp" not in installed:
        raise LifecycleCheckError("The installed base/web/core baseline is incomplete.")
    if any(name in OPTIONAL_MODULES or name.startswith("mfierp_")
            or info.get("license") in PROPRIETARY_LICENSES for name, info in installed.items()):
        raise LifecycleCheckError("CRM, Accounting, adapter or proprietary modules are outside this CE-absence lane.")
    if snapshot.get("optional_models"):
        raise LifecycleCheckError("Optional CRM/Accounting models are present in the registry.")
    if snapshot.get("mfierp_attachments"):
        raise LifecycleCheckError("MFIERP attachments exist; the empty synthetic test cannot discard them.")
    counts = snapshot.get("model_counts", {})
    if not REQUIRED_MODELS <= counts.keys():
        raise LifecycleCheckError("The installed MFIERP model baseline is incomplete.")
    for model, count in counts.items():
        if type(count) is not int or count < 0 or not model.startswith("mfierp."):
            raise LifecycleCheckError("Invalid core row-count evidence.")
        if model not in STATIC_MODELS and count:
            raise LifecycleCheckError("Tenant or transient form data exists; uninstall is refused without deleting it.")
    if counts.get("mfierp.capability", 0) <= 0:
        raise LifecycleCheckError("The installed static capability catalog is missing.")


def check_postflight(before, after):
    if after.get("core_state") != "uninstalled":
        raise LifecycleCheckError("The standard uninstall did not finish.")
    expected_modules = {key: value for key, value in before["installed_modules"].items() if key != "mfierp"}
    if after.get("installed_modules") != expected_modules:
        raise LifecycleCheckError("An unrelated installed module or version changed.")
    if any(after.get(key) for key in ("registered_models", "model_metadata", "field_metadata",
            "module_xmlids", "retained_owned_records", "retained_tables", "pending_modules", "optional_models",
            "mfierp_attachments")):
        raise LifecycleCheckError("MFIERP metadata, tables or pending module operations remain after uninstall.")
    if after.get("base_references") != before["base_references"]:
        raise LifecycleCheckError("A standard base reference was removed or changed.")


def perform_uninstall(before, uninstall, inspect_after):
    """Fail closed before mutation and never retry a failed/unknown uninstall."""
    check_preflight(before)
    uninstall()
    after = inspect_after()
    check_postflight(before, after)
    return after


def _installed_modules(env):
    return {item["name"]: {"version": item["latest_version"], "license": item["license"]}
        for item in env["ir.module.module"].search_read([("state", "=", "installed")],
            ["name", "latest_version", "license"])}


def _base_references(env):
    result = {}
    for xmlid in BASE_REFERENCES:
        record = env.ref(xmlid, raise_if_not_found=False)
        if not record or not record.exists():
            raise LifecycleCheckError("The standard base reference baseline is incomplete.")
        result[xmlid] = (record._name, record.id)
    return result


def _pending_modules(env):
    return env["ir.module.module"].search([("state", "in", ["to install", "to upgrade", "to remove"])]).mapped("name")


def _capture_owned_records(env, names):
    owned = defaultdict(set)
    xmlids = env["ir.model.data"].search_read([("module", "=", "mfierp")], ["model", "res_id"])
    for row in xmlids:
        if not row["model"].startswith("mfierp."):
            owned[row["model"]].add(row["res_id"])
    model_ids = env["ir.model"].search([("model", "in", names)]).ids
    for model, domain in (("ir.model", [("id", "in", model_ids)]),
            ("ir.cron", [("model_id", "in", model_ids)]),
            ("ir.access", [("model_id", "in", model_ids)]),
            ("ir.ui.view", [("model", "in", names)]),
            ("ir.actions.act_window", [("res_model", "in", names)]),
            ("ir.actions.server", [("model_id", "in", model_ids)])):
        owned[model].update(env[model].with_context(active_test=False).search(domain).ids)
    return {model: sorted(ids) for model, ids in owned.items()}, len(xmlids)


def _read_postflight(database, names, owned, tables):
    from odoo import SUPERUSER_ID, api
    from odoo.orm.registry import Registry
    from odoo.tools.sql import table_exists

    with Registry(database).cursor() as cursor:
        fresh = api.Environment(cursor, SUPERUSER_ID, {})
        return {"core_state": fresh["ir.module.module"].search([("name", "=", "mfierp")]).state,
            "installed_modules": _installed_modules(fresh), "pending_modules": _pending_modules(fresh),
            "registered_models": sorted(name for name in fresh.registry if name.startswith("mfierp.")),
            "model_metadata": fresh["ir.model"].search_count([("model", "in", names)]),
            "field_metadata": fresh["ir.model.fields"].search_count([("model", "in", names)]),
            "module_xmlids": fresh["ir.model.data"].search_count([("module", "=", "mfierp")]),
            "mfierp_attachments": fresh["ir.attachment"].search_count([("res_model", "in", names)]),
            "retained_owned_records": {model: fresh[model].browse(ids).exists().ids
                for model, ids in owned.items() if ids and model in fresh.registry
                and fresh[model].browse(ids).exists()},
            "retained_tables": sorted(table for table in tables if table_exists(cursor, table)),
            "optional_models": sorted(OPTIONAL_MODELS.intersection(fresh.registry.models)),
            "base_references": _base_references(fresh)}


def run(env, environ=None):
    if env is None:
        raise LifecycleCheckError("Supply this file to Odoo 20 shell on stdin; ordinary Python cannot run the database check.")
    # Import framework only inside the real shell; pure guard tests need no Odoo.
    from unittest.mock import patch

    from odoo import SUPERUSER_ID, release
    from odoo.modules.module import get_module_path

    environ = os.environ if environ is None else environ
    database = env.cr.dbname
    check_guard(database, environ.get("MFIERP_TEST_CORE_LIFECYCLE_DB"),
        environ.get("MFIERP_TEST_CORE_LIFECYCLE"), release.version_info[0],
        env.su is True and env.uid == SUPERUSER_ID)
    manifest = ast.literal_eval((Path(get_module_path("mfierp")) / "__manifest__.py").read_text(encoding="utf-8"))
    source_version = check_manifest(manifest)
    core = env["ir.module.module"].search([("name", "=", "mfierp")])
    if len(core) != 1:
        raise LifecycleCheckError("Exactly one installed core module record is required.")
    names = sorted(name for name in env.registry if name.startswith("mfierp."))
    before = {"core_state": core.state, "source_version": source_version, "installed_version": core.latest_version,
        "installed_modules": _installed_modules(env), "pending_modules": _pending_modules(env),
        "downstream_modules": core.downstream_dependencies().mapped("name"),
        "optional_models": sorted(OPTIONAL_MODELS.intersection(env.registry.models)),
        "mfierp_attachments": env["ir.attachment"].with_context(active_test=False).search_count([("res_model", "in", names)]),
        "model_counts": {name: env[name].with_context(active_test=False).search_count([]) for name in names},
        "base_references": _base_references(env)}
    check_preflight(before)
    owned, xmlid_count = _capture_owned_records(env, names)
    tables = {env[name]._table for name in names if env[name]._auto}
    # Standard Odoo API owns its commit and registry replacement. Never call
    # model unlink, clear audit rows or retry this operation on an unknown result.
    network_error = LifecycleCheckError("An outbound HTTP request was attempted; the lifecycle test is aborted.")
    with patch("requests.sessions.Session.request", side_effect=network_error), patch(
            "urllib.request.urlopen", side_effect=network_error):
        after = perform_uninstall(before, core.button_immediate_uninstall,
            lambda: _read_postflight(database, names, owned, tables))
    report = {"check": "CE_CORE_OPTIONAL_ABSENCE_UNINSTALL_PASS", "database": database,
        "odoo_version": release.version, "core_source_version": source_version,
        "core_dependencies": sorted(CORE_DEPENDENCIES), "business_and_form_rows": 0,
        "removed_models": names, "owned_xmlids_checked": xmlid_count,
        "owned_metadata_checked": {model: len(ids) for model, ids in sorted(owned.items())},
        "remaining_installed_modules": sorted(after["installed_modules"]),
        "optional_apps_absent": True, "external_requests": 0, "enterprise_evidence": "EE_NOT_TESTED"}
    print(json.dumps(report, sort_keys=True))
    return report


if __name__ == "__main__":
    run(globals().get("env"))
