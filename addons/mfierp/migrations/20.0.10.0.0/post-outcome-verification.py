# SPDX-License-Identifier: LGPL-3.0-or-later
"""Retain old outcome evidence without presenting response receipt as verification."""
from odoo import SUPERUSER_ID, _, api, fields


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    commands = env["mfierp.command"]
    while batch := commands.search([
            ("legacy_reclassified_at", "=", False), "|",
            "&", ("state", "=", "done"), ("preview_digest", "=", False),
            "&", ("state", "=", "remote_pending"), ("completed_at", "!=", False)], order="id", limit=500):
        for command in batch:
            command.write({
                "legacy_state": command.state,
                "legacy_completed_at": command.completed_at,
                "legacy_status_message": command.status_message,
                "legacy_reclassified_at": fields.Datetime.now(),
                "state": "remote_pending",
                "completed_at": False,
                "status_message": _("Historical outcome metadata retained as unverified evidence. Authoritative outcome verification is pending; this command will not be resent."),
            })
