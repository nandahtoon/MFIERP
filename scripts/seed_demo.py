"""Run only in a disposable Odoo demo database through `odoo shell`.

This adds synthetic snapshots and named test users, never sends a remote request,
and never enables synchronization. The caller owns the shell transaction commit.
"""
import os

from odoo import Command

if env.cr.dbname != "mfierp_demo":
    raise RuntimeError("Demo seeding is restricted to database mfierp_demo.")
if env["mfierp.backend"].search_count([]):
    raise RuntimeError("Demo database already has connections; refusing to seed again.")

backend = env["mfierp.backend"].create({
    "name": "DEMO — Synthetic Portfolio", "base_url": "https://demo.invalid/fineract-provider/api/v1",
    "tenant": "demo", "sync_enabled": False,
})
records = env["mfierp.record"]
records._upsert(backend, "office", {"id": 1, "name": "DEMO Head Office"})
client = records._upsert(backend, "client", {"id": 101, "displayName": "DEMO Aye Chan", "accountNo": "C-000101",
    "status": {"value": "Active"}, "officeName": "DEMO Head Office", "activationDate": [2026, 10, 1]})
records._upsert(backend, "group", {"id": 10, "name": "DEMO Community Group", "status": {"value": "Active"}})
records._upsert(backend, "center", {"id": 20, "name": "DEMO Township Center", "status": {"value": "Active"}})
records._upsert(backend, "loan_product", {"id": 1, "name": "DEMO Small Business Loan", "currency": {"code": "USD"},
    "interestRatePerPeriod": 1, "numberOfRepayments": 12, "transactionProcessingStrategyCode": "mifos-standard-strategy"})
records._upsert(backend, "savings_product", {"id": 1, "name": "DEMO Everyday Savings", "currency": {"code": "USD"}})
loan = records._upsert(backend, "loan", {"id": 201, "accountNo": "LN-000201", "status": {"value": "Active"},
    "clientName": client.name, "officeName": "DEMO Head Office", "loanProductName": "DEMO Small Business Loan",
    "currency": {"code": "USD"}, "principal": 1200, "summary": {"totalOutstanding": 980}})
loan._replace_lines({"repaymentSchedule": {"periods": [
    {"period": i, "dueDate": [2026, i + 6, 1], "totalDueForPeriod": 110, "totalOutstandingForPeriod": 110, "complete": False}
    for i in range(1, 7)]}, "transactions": [{"id": 301, "type": {"value": "Repayment"}, "date": [2026, 11, 1], "amount": 110}]})
records._upsert(backend, "savings", {"id": 401, "accountNo": "SV-000401", "status": {"value": "Active"},
    "clientName": client.name, "currency": {"code": "USD"}, "summary": {"accountBalance": 425}})
env.ref("base.user_admin").write({"group_ids": [Command.link(env.ref("mfierp.group_manager").id)],
    "password": os.environ["MFIERP_DEMO_PASSWORD"]})
for login, group, label in [("maker", "group_operator", "Demo Maker"), ("checker", "group_checker", "Demo Checker")]:
    env["res.users"].create({"name": label, "login": login,
        "password": os.environ["MFIERP_DEMO_PASSWORD"],
        "company_id": env.company.id, "company_ids": [Command.set(env.company.ids)],
        "group_ids": [Command.set([env.ref("mfierp." + group).id])]})
print("Seeded synthetic demo data. No remote requests sent.")
