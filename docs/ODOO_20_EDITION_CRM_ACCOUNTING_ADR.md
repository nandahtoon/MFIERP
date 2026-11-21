# ADR 002 — Odoo 20 Community + Enterprise with optional CRM and Accounting

Decision date: 2026-11-19. **Owner-approved target; not implemented or accepted in Enterprise yet.** This supplements ADR 001. The project's core goal remains full source-backed Mifos X operator-workflow parity with Fineract holding the canonical microfinance ledger.

## Decision and release model

The existing `mfierp` module stays **edition-neutral** and installable on both Odoo 20 Community (CE) and licensed Enterprise (EE). It must not hard-depend on `account`, `crm`, an EE-only addon or Enterprise code. Current manifest depends on `base`, `web`; this is a suitable core dependency baseline, NOT evidence EE installation was tested.

Provide independently installable modules:

| Target addon | Dependency | Edition | Responsibility |
| --- | --- | --- | --- |
| `mfierp` | `base`, `web` | CE + EE | Fineract operations, portfolio read projections, maker/checker, audit and task UI |
| `mfierp_crm` | `mfierp`, `crm` | CE + EE if CRM is present | Explicit lead/opportunity/contact ↔ Fineract client mapping and approved onboarding |
| `mfierp_account` | `mfierp`, `account` (check actual 20.0 model/edition availability) | CE + EE where compatible `account` components are installed | Source-mapped accounting ownership, GL comparison, read-only reconciliation; posting bridge optional, OFF by default |
| `mfierp_account_enterprise` or a narrowly scoped EE addon | Core plus *verified* EE-only dependencies | Licensed EE only | Optional EE feature integration, without importing/requiring it in CE/core |

Use Odoo native `res.partner`, `crm.lead`, `account.account`, `account.move` only through the corresponding installed app/adapter. Do not hardcode EE XML view IDs or symbols in the core. Odoo 20 dependency names, constraints, ACL, models and views must be validated against the actual edition sources. No Odoo 16/17/18-specific assumptions, no monkey-patching proprietary modules.

## CRM — explicit two-system mapping, not automatic client duplication

**Odoo owns:** leads/opportunities, CRM stages, sales activities, contact communications and local marketing/sales process.
**Fineract owns:** microfinance client account identity, activation/status, customer-side credit/savings and all related financial records.
**MFIERP owns:** approved crosswalk and link workflow.

Mandatory crosswalk keys: Odoo company and partner, Fineract connection/tenant + immutable client ID, optional lead, external reference, last verified timestamp, mapping origin, consent/authorization evidence. Unique constraints and manual conflict resolution prevent wrong or duplicated links. Sensitive client KYC fields must be minimized, protected and separately retained according to policy.

Flow: CRM lead → qualify and check consent/KYC → link/create `res.partner` → maker prepares reviewed Fineract client create/link → distinct checker approves if remote write required → verify Fineract ID/status → create idempotent crosswalk → show only authorized client/account context. **CRM Won MUST NOT auto-create or auto-activate a Fineract client.** Names/emails/phones are not sufficient for silent identity matching. Existing Fineract client may be linked to a partner only through a verified explicit procedure.

Do not implement unrestricted bidirectional sync. Specify per-field authority, allowlists, timestamps, privacy, conflict queue and anti-loop behavior. CRM-only roles must not see loan balances, repayment histories or protected PII. Permit contextual smart buttons only with company+office+tenant security checks on RPC as well as UI.

## Accounting — one economic transaction, explicit ledger ownership

**Fineract authority:** loan/savings subledger, account balances, principal, interest, accruals, penalties/fees, repayment allocation and microfinance journal/GL.
**Odoo ERP authority:** independently originated Odoo business transactions (vendor bills, overhead, invoices for non-microfinance services, enterprise purchasing, expenses, internal ERP accounting).
**Cross-system financial statements:** must document consolidation boundary, inter-ledger elimination/settlement, mapping and reconciliation; never sum the same principal/interest/income twice.

Default `READ_ONLY_RECONCILIATION` mode: show authorized Fineract GL/journal/trial balance alongside Odoo ERP chart/journal summaries with mapped accounts, dates, amount and currency. Report mismatches and record verified sources. Do not make any `account.move` as a side effect of loan commands or a generic Fineract POST response.

Separate **opt-in CONTROLLED_GL_BRIDGE** (OFF and BLOCKED pending signed finance policy): after an independent senior accountant and owner approve a formal source-to-destination GL boundary, allow **balanced, summarized, reviewed journal batches** from independently verified Fineract source journals into the Odoo consolidated ERP ledger. This is a mapped financial reporting import, NOT a second loan subledger or duplicate per-loan posting. Required:
- Journal/account mappings, legal company, Fineract tenant, business and effective date, period, currency/FX policy, precision, signs, office/suspense/clearing accounts, tax and closed periods
- Deterministic unique source batch key (tenant/company/source journal/period/version/hash), immutable audit, idempotent import, duplicate prevention, source ↔ target reference, debit=credit test on each side
- Preview/dry run, independent accountant sign-off, mandatory reconciliation of Fineract GL and Odoo target balances, discrepancy quarantine and controlled reversals
- No auto retry after ambiguous Odoo posting/HTTP state; no Odoo-to-Fineract financial echo; no automatic mode switch
- Explicitly prevent double counting between Fineract portfolio assets/liabilities/income and Odoo consolidated reports, accounting basis and ownership clarified

If the business needs Odoo as **enterprise-wide consolidated GL**, document that as the approved reporting/posting architecture, with Fineract loan GL as authoritative source subledger and mapped consolidated journals (not competing transaction masters). Never silently change primary financial ownership. Normal independent Odoo ERP invoices and bills remain in Odoo.

CE Accounting capability is not identical to EE full Accounting. Investigate the actual `account` models/features available to each tested edition. If a CE feature is missing, show a documented capability limit or separately reviewed compatible community addon; do not copy Enterprise proprietary code, promise Enterprise accounting features in CE, or block unrelated MFIERP core. EE-only bank reconciliation, advanced reports/assets/consolidation go in licensed optional extensions as applicable.

## Supported deployment paths and licensing

Testing targets: CE core; CE+CRM; CE+available-account; EE core; EE+CRM+Accounting; EE-specific addon when licensed. Native Python custom addons are intended for self-hosted Odoo or Odoo.sh where supported. **Do not claim ordinary Odoo Online SaaS is supported**: Odoo Online does not host normal custom Python modules.

Keep LGPL-3-compatible MFIERP code, license/attribution review and Enterprise-only third-party source/assets out of the repository. Enterprise verification requires a licensed EE test runner/database; CE green CI never establishes EE green. If EE cannot be tested, report `EE_NOT_TESTED` and keep release claim blocked.

## Codex requirements and acceptance tests

WP-ERP-01: audit manifest, models and Odoo 20 CE+EE module portability; separate optional addons, install/upgrade/uninstall and optional app absence tests. Core stays dependency-light.
WP-ERP-02: CRM mapping model, consent, workflow, dedupe, direct-RPC ACL, lead→contact→reviewed Fineract client submission and remote correlation; read-only and authorized synthetic live tests.
WP-ERP-03: Accounting read-only account map, source GL/trial balance comparisons, difference report, accounting ownership tests, correct currency/date/office.
WP-ERP-04: Controlled GL bridge **only after** owner+senior accounting design approval: balanced summarized entries, unique source batch, accountant dual control, closed-period/multi-currency validation, reversal, duplicate/timeout tests and separately authorized synthetic UAT. Keep disabled otherwise.
WP-ERP-05: EE-specific optional features and all CE/EE installation, workflow, security, performance and migration compatibility evidence.

Test complete CE/EE matrix with true edition-specific binaries/dependencies. Test cross-company/office/tenant leakage, unauthorized CRM role balances, ambiguous names, duplicate records, unlink/relink, revoked rights, source drift, lost responses, mismatched GL account mapping, double posting prevention, trial balance, dates/currencies/FX, closed periods, missing EE module and safe uninstall.

**Acceptance labels:** `CE_CORE_PASS`, `CE_CRM_PASS`, `CE_ACCOUNT_PASS`, `EE_CORE_PASS`, `EE_CRM_ACCOUNT_PASS`, `ERP_GL_RECONCILED`, `GL_BRIDGE_APPROVED`, `GL_BRIDGE_UAT_PASS`. Each needs exact-head/source, test run and acceptance evidence. The GL posting bridge may be explicitly excluded/disabled by owner policy, but cannot be called implemented; CE+EE overall support cannot be declared while EE is not tested.

All existing MFIERP safety boundaries remain mandatory: never modify existing Oracle financial/customer data, rotate credentials, merge or deploy without a separate authorized action. Future Codex work must keep progress on independent safe tasks while RED finance/hosting/production decisions remain blocked.

## Reference documentation

- https://www.odoo.com/documentation/20.0/developer/reference/backend/module.html
- https://www.odoo.com/page/editions
- https://www.odoo.com/documentation/20.0/applications/sales/crm/acquire_leads/convert.html
- https://www.odoo.com/documentation/20.0/applications/finance/accounting.html
- https://www.odoo.com/documentation/20.0/administration/odoo_sh/getting_started/create.html
