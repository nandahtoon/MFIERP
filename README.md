# MFIERP — MiFosXinOdoo

Native Odoo 20 screens for Mifos X operations, backed by Apache Fineract. The required target covers Community and Enterprise; current runtime evidence is Community only. Fineract owns the financial engine; Odoo provides the operator workspace, company boundaries, maker/checker workflow and command audit register.

## Included

- Company/tenant connections with environment-based credentials and verified HTTPS.
- Native clients, groups, centers, loan/savings products, loan/savings accounts, offices, staff, charges, GL accounts, journals and report catalogs.
- 21 typed write operations: client/group/center creation and activation; individual loan application, approval, disbursement, rejection, withdrawal, repayment, write-off and closure; savings application, approval, activation, rejection, deposit, withdrawal and closure.
- Account balances, remote repayment schedules, transaction history and charges; native table report execution.
- Separate makers/checkers, immutable payload hashes, durable dispatch reservation, idempotency keys and manual reconciliation of unknown outcomes.
- Response and completion timestamps are separate. Mutations stay pending until a reviewed authoritative verifier exists; financial applied completion is currently blocked. Historical response confirmations retain their audit evidence during upgrade.
- Successful mutating responses stay Remote Verification Pending, even with a resource ID. Applied completion is currently available only for independently verified scheduler start/stop; financial readback verifiers remain unimplemented.
- Odoo 20 `ir.access` security, multi-company isolation, bounded synchronization, service tests and Odoo workflow/security tests.
- Extended native workspace compiled from 966 deployed Fineract API operations, with 108 separately reviewed Mifos command variants: 945 typed contracts and 152 explicitly blocked contracts.
- Nested typed forms and repeated rows, protected document uploads/downloads, administrator-only configuration and deployment-secret references. All writes enter independent approval and the existing dispatch audit.
- Registered Fineract datatable discovery and typed entry reads, creation, updates and deletion, with pinned metadata and independent approval for writes.
- Source-reviewed standing-instruction editing, provisioning criteria, share dividend planning/approval and administrator-reviewed scheduler controls, explicit bulk officer reassignment, holiday activation and savings tax withholding.

## Get started

See [deployment instructions](docs/DEPLOYMENT.md). The local developer app uses <http://localhost:18069> and an isolated Compose project. No Fineract server is bundled, and existing financial services are not modified.

## Project contract

| Document | Purpose |
| --- | --- |
| [Coverage](docs/COVERAGE.md) | Supported workflows, explicit gaps and live acceptance sequence |
| [Architecture](docs/ARCHITECTURE.md) | Authority boundaries, transaction safety, roles and version policy |
| [Governance](docs/GOVERNANCE.md) | Coding/review rules, release gates and incident handling |
| [Sources](docs/SOURCES.md) | Pinned MFIERP, Odoo 19/20, Mifos X and Fineract research provenance |
| [Validation](docs/VALIDATION.md) | Checks actually performed and remaining acceptance work |
| [Outcome verification](docs/OUTCOME_VERIFICATION.md) | Pending response semantics, reconciliation limits and 20.0.10.0.0 upgrade impact |
| [Oracle staging](docs/ORACLE-STAGING.md) | Discovered hosting, runtime provenance and credential boundary |
| [Functional matrix](docs/parity/README.md#wp00-functional-inventory) | Pinned screen/action evidence obligations, current gaps and reproducible extraction |
| [Work package plan](docs/parity/WORK_PACKAGE_PLAN.md) | Dependency order, exact implementation evidence and external acceptance gates |
| [Agent conventions](AGENTS.md) | Rules for future coding work |

The target is Odoo 20; Odoo 19 requires a separate security backport. API form coverage does not establish complete Mifos X feature parity. The [source inventory](docs/parity/README.md) records remaining contract, workflow and acceptance work. Its 8,063 extraction/review obligations include 748 component screens; no workflow is operator-accepted or live-UAT-passed. The row count is not an approved feature denominator. Financial production acceptance requires verification against the intended Fineract version and tenant products.

The addon is licensed under LGPL-3.0-or-later. No upstream Angular or Java application code is vendored.

## Codex full-parity implementation charter

For the owner-approved full Mifos X operator parity objective, see [Codex Master Implementation Specification](docs/CODEX_MASTER_IMPLEMENTATION_SPEC.md) and [Parity Acceptance Matrix](docs/PARITY_ACCEPTANCE_MATRIX.md). These distinguish API-contract coverage, completed workflows and authenticated financial UAT. The development target is full source-backed end-to-end workflow coverage, not a pilot-only release or a catalog of API forms. All staging/production mutation and release approvals remain separate.


## Dual-edition ERP target (not yet implemented)

The owner-approved future design targets Odoo 20 **Community and Enterprise**. The core MFIERP addon remains lightweight and independent of Odoo CRM/Accounting; optional `mfierp_crm`, `mfierp_account` and licensed Enterprise adapter addons provide native integration only when installed. Currently these bridges are NOT implemented or tested in EE. See [ADR 002](docs/ODOO_20_EDITION_CRM_ACCOUNTING_ADR.md) and [Codex master](docs/CODEX_MASTER_IMPLEMENTATION_SPEC.md). Fineract remains the canonical microfinance ledger, Odoo handles its own ERP accounting; cross-system consolidated postings are separately approved and off by default.
