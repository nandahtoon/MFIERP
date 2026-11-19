# MFIERP development conventions

MFIERP is the source of truth for this integration. Read README.md and docs/ before changing financial workflows.

- Target Odoo 20 Community with native views. Fineract owns balances, schedules, interest, charges, transactions and its ledger.
- Follow Odoo model, method, file naming and translation conventions. No financial calculations in the UI.
- Enforce authorization in Python as well as views. All tenant data must have a company boundary.
- Never accept arbitrary remote paths, commands or payloads from RPC. Use the operation registry and typed wizard.
- External writes require a distinct maker and checker. A dispatch whose result is unknown must never be retried automatically.
- Credentials belong in the deployment environment, never in records, logs or source control.
- Run unit tests and the Odoo installation/security/workflow tests after meaningful changes. Keep source and coverage documentation current.
- Do not modify other local services or databases. Use the isolated Compose project for tests.
