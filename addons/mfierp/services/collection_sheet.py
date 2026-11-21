# SPDX-License-Identifier: LGPL-3.0-or-later
"""Bounded collection-preview projection. Amounts are copied, never calculated."""
import math


def _text(value, limit):
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError("Collection labels must be text.")
    return value[:limit]


def project_preview(data):
    if not isinstance(data, dict) or not isinstance(data.get("clients"), list):
        raise ValueError("Collection preview must contain a client list.")
    rows, seen = [], set()
    truncated = len(data["clients"]) > 200
    for client in data["clients"][:200]:
        if not isinstance(client, dict):
            raise ValueError("Invalid collection client.")
        for key, kind, identifier, amount in [("loans", "Loan", "loanId", "totalDue"), ("savings", "Savings", "savingsId", "dueAmount")]:
            accounts = client.get(key) or []
            if not isinstance(accounts, list):
                raise ValueError("Invalid collection account list.")
            for account in accounts:
                if len(rows) >= 500:
                    truncated = True
                    break
                if not isinstance(account, dict):
                    raise ValueError("Invalid collection account.")
                remote_id = account.get(identifier)
                if isinstance(remote_id, bool) or not isinstance(remote_id, int) or remote_id < 1 or (kind, remote_id) in seen:
                    raise ValueError("Invalid or duplicate collection account ID.")
                seen.add((kind, remote_id))
                due, charges = account.get(amount), account.get("chargesDue")
                for value in [due, charges]:
                    if value is not None:
                        if isinstance(value, bool) or not isinstance(value, (int, float)):
                            raise ValueError("Collection amounts must be finite remote numbers.")
                        try:
                            finite = math.isfinite(value)
                        except OverflowError as exc:
                            raise ValueError("Collection amount exceeds the supported range.") from exc
                        if not finite:
                            raise ValueError("Collection amounts must be finite remote numbers.")
                rows.append({"client": _text(client.get("clientName"), 250), "kind": kind, "remote_id": remote_id,
                    "product": _text(account.get("productName"), 250), "due": due, "charges": charges,
                    "currency": _text(account.get("currencyCode"), 20)})
    options = data.get("paymentTypeOptions") or []
    if not isinstance(options, list):
        raise ValueError("Invalid payment type options.")
    return {"rows": rows, "truncated": truncated, "payment_types": [
        {"id": option["id"], "name": _text(option.get("name"), 250)}
        for option in options[:100] if isinstance(option, dict) and isinstance(option.get("id"), int)
        and not isinstance(option["id"], bool) and option["id"] > 0]}
