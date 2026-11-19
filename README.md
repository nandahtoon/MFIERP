# MFIERP — MiFosXinOdoo

Native Odoo 20 Community screens for Mifos X operations, backed by Apache Fineract. Fineract owns the financial engine; Odoo provides the operator workspace, company boundaries, maker/checker workflow and command audit register.

## Included

- Company/tenant connections with environment-based credentials and verified HTTPS.
- Native clients, groups, centers, loan/savings products, loan/savings accounts, offices, staff, charges, GL accounts, journals and report catalogs.
- 21 typed write operations: client/group/center creation and activation; individual loan application, approval, disbursement, rejection, withdrawal, repayment, write-off and closure; savings application, approval, activation, rejection, deposit, withdrawal and closure.
- Account balances, remote repayment schedules, transaction history and charges; native table report execution.
- Separate makers/checkers, immutable payload hashes, durable dispatch reservation, idempotency keys and manual reconciliation of unknown outcomes.
- Odoo 20 `ir.access` security, multi-company isolation, bounded synchronization, service tests and Odoo workflow/security tests.
- Extended native workspace compiled from 966 deployed Fineract API operations, with 68 separately reviewed Mifos command variants: 884 typed contracts and 152 explicitly blocked contracts.
- Nested typed forms and repeated rows, protected document uploads/downloads, administrator-only configuration and deployment-secret references. All writes enter independent approval and the existing dispatch audit.

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
| [Oracle staging](docs/ORACLE-STAGING.md) | Discovered hosting, runtime provenance and credential boundary |
| [Agent conventions](AGENTS.md) | Rules for future coding work |

The target is Odoo 20; Odoo 19 requires a separate security backport. API form coverage does not establish complete Mifos X feature parity. The [source inventory](docs/parity/README.md) records remaining contract, workflow and acceptance work. Financial production acceptance requires verification against the intended Fineract version and tenant products.

The addon is licensed under LGPL-3.0-or-later. No upstream Angular or Java application code is vendored.
