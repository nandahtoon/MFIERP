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

## Codex master execution mandate — future sessions

For the full Mifos X native Odoo goal, READ docs/CODEX_MASTER_IMPLEMENTATION_SPEC.md and docs/PARITY_ACCEPTANCE_MATRIX.md before planning or editing. Treat these as the owner-approved target contract and execution sequence, together with the existing ADRs and AGENTS rules. The end goal is full verified operator workflow parity, NOT API-contract percentage or pilot-only completion. Maintain the source-to-feature matrix, solve gaps in safe increments, keep exact-head test/UAT evidence, and never report 100% without every explicit acceptance gate.

Start at WP00 (inventory and traceability), then proceed through the master work packages on the next genuinely unblocked increment. Preserve Fineract authority, existing Odoo implementation, company/office/tenant boundaries and dual control. Do not merge or deploy, mutate Oracle financial data, alter credentials or change other repos without a separately authorized handoff. Use MFIERP GitHub issue [Codex master] once created as the task tracker and PR #1 as current implementation context.
