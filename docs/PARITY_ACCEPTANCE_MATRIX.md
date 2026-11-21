# MFIERP — 100% Parity Acceptance Matrix: Baseline and Template

Scope: full operator-level functional parity with the owner-approved pinned Mifos X source, using native Odoo 20 Community and Fineract authoritative remote financial engine. Full instructions are in CODEX_MASTER_IMPLEMENTATION_SPEC.md.

Do NOT calculate total product completion from typed API count. Baseline observed 2026-11-19: 1,094 static contracts, 942 typed/152 blocked; 720 inspected literal Mifos calls (662 typed candidates / 30 requires source work / 25 computed resource review / 3 not in deployed published metadata). All operator_workflow_verified and live_uat_verified flags currently unverified in source inventory. Newly added 20.0.8.0.1 safety changes passed exact-head CI, but authenticated Oracle synthetic UAT has not been completed.

The table below is a **domain inventory checkpoint**, not a declaration that a domain is complete:

| ID | Domain | Evidence starting point | Current classification | Gate to complete |
|---|---|---|---|---|
| D01 | Organization & admin | Native office/staff reads; selected API contracts | PARTIAL, UAT_UNVERIFIED | Office hierarchy/user/role/settings native flows plus approved Fineract integration |
| D02 | Clients/KYC | Core create/activate; datatables/documents API forms | PARTIAL, UAT_UNVERIFIED | Full source-backed KYC/lifecycle/exception browser+live UAT |
| D03 | Groups/centers | Membership/calendar/attendance typed flows | PARTIAL, UAT_UNVERIFIED | Complete source workflows, JLG behavior and permissions |
| D04 | Individual loans/products | 21 focused operations shared with other domains | PARTIAL, UAT_UNVERIFIED | All loan stages, money/ledger, exceptions and reversals |
| D05 | Advanced lending | Reschedule typed paths, JLG/GLIM gaps | PARTIAL, UAT_UNVERIFIED | Source-backed advanced flows, negative and remote UAT |
| D06 | Savings | Basic lifecycle/cash | PARTIAL, UAT_UNVERIFIED | Holds/fees/interest/tax/reversal, complete account journey |
| D07 | Fixed/recurring deposits | Source-reviewed cash and lifecycle contracts | PARTIAL, UAT_UNVERIFIED | Full maturity/settlement and accounting UAT |
| D08 | Shares/dividends | Dividend plan/approval and reconciliation pending | PARTIAL, UAT_UNVERIFIED | Payout/approval/account evidence |
| D09 | Charges/standing instructions/transfers | Typed standing-instruction update, selected charges | PARTIAL, UAT_UNVERIFIED | Full source-backed charge/transfer lifecycle |
| D10 | Collection | Individual preview/posting, per-account reconcile | PARTIAL, UAT_UNVERIFIED | Group/bulk/field procedures and remote posting evidence |
| D11 | Cash/branch controls | Not fully inventoried | NOT_MAPPED | Approved cash custody/accounting boundary & end-of-day task journey |
| D12 | Accounting/GL | Fineract GL read/catalog/provisioning references | PARTIAL, UAT_UNVERIFIED | Full finance controls and GL/trial balance reconciliation |
| D13 | Reports/analytics | Table report and catalog read | PARTIAL, UAT_UNVERIFIED | Source reports, filters/exports, roles and matching figures |
| D14 | Documents/datatables/surveys | Registered datatable entry forms, protected files | PARTIAL, UAT_UNVERIFIED | Schema/inline forms and questionnaire lifecycle |
| D15 | Bulk/migration | Not end-to-end implemented | NOT_MAPPED | Import templates, preview, authorization, remote reconcile |
| D16 | Audit/permissions | Company & maker/checker present | PARTIAL, UAT_UNVERIFIED | Office scope, Fineract audit, PII retention/security review |
| D17 | Tasks/notifications/recovery | Command state/reconcile register | PARTIAL, UAT_UNVERIFIED | Complete operator inbox, exception paths and recovery |
| D18 | Integration surfaces | Typed v1/v2 API registry | PARTIAL, UAT_UNVERIFIED | Contract compatibility, version drift, external owner boundaries |
| D19 | UX/accessibility | Native views; localized Playwright smoke checks | PARTIAL, UAT_UNVERIFIED | End-to-end task UX incl. responsive/keyboard/200% zoom |
| D20 | Reliability/commercial ops | Basic sync, Docker local, CI | PARTIAL, UAT_UNVERIFIED | Incremental sync, office load, backups, DR, support/release gates |

## How to convert this into checkable 100% evidence

Codex must create docs/parity/FULL_FUNCTIONAL_MATRIX.csv as a row-per-source-action/tenant-workflow artifact, not merely mark each domain DONE. Fields and states are specified in CODEX_MASTER_IMPLEMENTATION_SPEC.md Section 4. Include negative, reversal and remote-financial side effects for actions which can change money.

Minimum acceptance on every row: source mapping, exact API/command, native screen context and form validation, permissions, unit test, relevant Odoo browser test, integration/UAT evidence, independent review and owner acceptance. Source-unsupported features must be classified UPSTREAM_BLOCKED, never described as already working. Owner-approved inapplicable exclusions are tracked, not counted as full delivered capability.

Track two independent completion percentages only after validated source inventory:
- **Contract verification**: source-reviewed executable operation contracts divided by reviewed in-scope contract obligations.
- **Operator parity**: accepted end-to-end operator workflows divided by approved in-scope workflows.
Never equate them. Keep live UAT percentage independent from either.

## Critical walkthroughs to demonstrate

1. Login as branch Reader / Maker / Checker / Admin → correct company/office/task visibility.
2. New client → KYC → submit/activate → remote readback → group/office relationship.
3. Individual loan application → approve → disburse → reconcile GL and remote schedule → repayment/reversal → close.
4. Savings opening → deposit/withdraw → interest/charges → remote balance/reversal → close.
5. Group meeting → attendance → collection preview → separate approval → post → per-account reconciliation.
6. Configure product/COA/provisioning with independent review → Fineract reports/trial balance.
7. Scheduler/admin workflow → empty response → independently verify actual state via authenticated GET.
8. Network timeout / 500 / crash after persisted reservation → zero duplicate money movements, manual reconciliation.
9. Migration/bulk dry run → verify, approve, execute only in approved synthetic target → per-row reconciliation.
10. Office isolation and revoked permissions tested through direct RPC, report/export and record contexts.

**Release prohibited** until every mandatory gate in the master specification is satisfied.


## Owner amendment: Odoo 20 CE / EE ERP integration gates

| Gate | Required user outcome | Actual status as of mandate | Evidence needed |
| --- | --- | --- | --- |
| ERP-01 | Edition-neutral MFIERP core on Odoo 20 CE and EE | CE tests pass; EE untested | Clean install + upgrade + security + browser tests per edition |
| ERP-02 | Optional CRM lead/partner/client mapping and approved Fineract onboarding | Not implemented | Native flow, permissions, duplicate and consent tests, synthetic UAT |
| ERP-03 | Optional Odoo Accounting read-only GL mapping/reconciliation | Not implemented | Account map, source-vs-target comparison, ACL and accounting review |
| ERP-04 | Optional summarized GL posting bridge, disabled by default | Not implemented, requires separate RED financial approval | Signed ownership/mapping and accountant approval, duplicate-safe balanced batch UAT |
| ERP-05 | Licensed Enterprise-specific enhancements | Not implemented | Independent EE-only module test, CE core unaffected |

See docs/ODOO_20_EDITION_CRM_ACCOUNTING_ADR.md. API form count alone does not establish edition, CRM or Accounting acceptance.
