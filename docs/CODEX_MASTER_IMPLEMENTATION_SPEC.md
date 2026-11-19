# MFIERP — Codex Master Implementation Specification (Full Mifos X Operator Parity)

Status: OWNER-DIRECTED IMPLEMENTATION TARGET; this is a specification, NOT evidence of completion or authorization to merge/deploy.
Last reviewed: 2026-11-19. Baseline feature branch: feat/odoo20-mifos-native. Owner's goal: complete, reliable, commercial-ready, low-complexity, productive native Odoo 20 Community user experience comparable to the relevant Mifos X operator workflows, powered by Apache Fineract.

## 0. Non-negotiable north star

Deliver an Odoo 20 Community native operator application with 100% VERIFIED parity against an explicitly inventoried, owner-approved Mifos X / Fineract target feature set, not simply 100% generated API forms. Preserve capabilities already implemented; fill, validate and integrate the missing workflow, operational controls, administration, reporting and usability gaps. Complete in evidence-backed increments, not one giant unreviewed change. "100%" is an acceptance goal, NEVER a status until the exit gate in Section 12 is satisfied.

Full parity means an operator can finish the relevant business task in Odoo without opening Mifos X, with remote Fineract outcomes demonstrably correct. Do not interpret Mifos X UI parity as a request to rewrite Apache Fineract or its ledger. For in-scope features not supported by the deployed Fineract version, record an upstream capability blocker with owner decision; never counterfeit functionality or claim parity.

There is no fixed calendar deadline or authorized production release in this mandate. Keep working on independent unblocked local/repository increments; stop at genuinely external, financial, infrastructure or policy approvals.

## 1. Sources of truth and source review

1. This repository nandahtoon/MFIERP owns ONLY the Odoo integration/operator workspace. Read its AGENTS.md, README.md, docs/ARCHITECTURE.md, docs/GOVERNANCE.md, docs/COVERAGE.md, docs/VALIDATION.md, docs/parity/README.md, docs/ORACLE-STAGING.md, docs/SOURCES.md, docs/DEPLOYMENT.md, and this specification at the exact checked-out commit.
2. Functional reference: nandahtoon/Mifosx-web-app at source revision 34c7f278861ef25052f2e00d106d8527f5d270d3. Review real screen/menu/action components, data sources, endpoint selection, submit transformations, dates, statuses, errors, and navigation. Confirm any later changed source independently, and re-pin the referenced commit rather than silently following latest.
3. Backend behavioral authority: Apache Fineract REST API, reviewed upstream implementation and the approved runtime's published OpenAPI. The current pinned deployed OpenAPI snapshot is Fineract 1.16.0-SNAPSHOT; use exact tested version/commit in the runtime and verify any mismatch explicitly.
4. Existing catalog/inventory artifacts: addons/mfierp/services/catalog.json and docs/parity/mifos-endpoints.json. Baseline: 966 published operations + 106 source-reviewed fixed command variants + 22 commandless reviewed forms = 1,094 contracts; 942 typed, 152 blocked. Comparison inventory: 720 literal calls from 99 Mifos service/routing source files; 662 typed candidates, 30 source-contract gaps, 25 computed-resource review items, 3 absent from published OpenAPI. These are coverage inputs, NOT percent-complete feature/UAT evidence.
5. Reference infrastructure and program boundaries: nandahtoon/MicroOps-Infra, nandahtoon/MicroOps-360-Fineract-Org. Infrastructure and existing Fineract/Web runbooks remain owned there. Do not edit these repositories, create an alternative runtime, or silently reinterpret their requirements.
6. Historical staging evidence: read-only proof (MicroOps-Infra Issue #30) had Offices=1, Staff=0, Users=3, Roles=2; credentials passed read-only authentication. It is historical, not today's acceptance. Treat missing staff and dirty runtime provenance as potential blockers to be revalidated through an authorized lane.

If one source conflicts with another, record a decision log with revision/path/line/evidence. Financial semantics from Fineract take precedence; owner-approved architectural boundary and security rules remain binding. Do not invent an API or use a frontend display contract as a financial authorization source.

## 2. Authority, data ownership, and anti-goals

- Fineract is the only canonical system for clients/loans/savings and their lifecycle outcomes, financial transactions, balances, interest, penalties, charges, repayments, repayment allocation, business date, provisioning effects, journal/GL ledger. Its accounting and balances must match independently verified remote results.
- Odoo is the native operator UI, integration configuration, cache/projection, independent maker/checker queue, command audit/reconciliation evidence, permissions and operational dashboard. Where Odoo ERP processes are later required, define explicit mapping and posting ownership; do NOT automatically duplicate Fineract GL entries into Odoo account.move.
- No Fineract source fork, no remote database writes/reads bypassing supported APIs, no embedded Mifos Angular iframe, no browser-held Fineract service secrets, no duplicate loans/ledger engine, no speculative MicroOps backend, no second tenant or cloned Oracle stack merely to avoid a missing feature.
- MFIERP's company is an Odoo security boundary; a Fineract tenant is a distinct deployment/identity concept. One tenant may be shared only under explicit security/segregation approval; default tenant does not magically imply per-company security.
- UI forms and local snapshots must never assert financial truth without a fresh Fineract read. Show an explicit as-of/detail-refresh timestamp, stale status, currency and source.
- Favor native Odoo 20 Community models, views and actions over custom frontend framework. Keep narrow service adapters, stable tested contracts, small dependencies, simple Compose development footprint and affordable operations.
- Commercial readiness includes licensing/attribution, tenant/company/office access rules, supportability, versioned install/migration, durable backups and audit controls. It does NOT automatically authorize SaaS multi-tenancy, billing/subscriptions or live customer onboarding. Document such future architecture separately.

## 3. Definition of 100% functional parity

A feature is COMPLETE only when ALL of these are proved at the same exact source/runtime version:
A. Target Mifos X screens/actions, user goal and upstream side effects are inventoried (including negative/cancel/reverse paths).
B. Source-backed exact Fineract method/path/query/command/body/response and permissions are documented; deviations are independently reviewed.
C. A named role can reach it via task-oriented native Odoo menus, record-context links and integrated forms; no arbitrary endpoint/command/payload typing.
D. Validation uses live tenant reference choices and correct status, mandatory fields, business dates, product restrictions, precision, currency and conditional rules.
E. Odoo server enforces maker/checker, office/company boundaries, immutable reviewed payloads and command ordering where applicable; tests prove forbidden paths fail.
F. State transitions safely handle success, remote maker/checker pending, timeout, 4xx, 5xx, unknown success, idempotency/correlation, crashes and manual reconciliation; no automatic replay of unknown money movement.
G. Remote financial records/schedule/transactions/ledger are independently re-read and compared, not locally recomputed or presumed from a POST response.
H. Python unit + Odoo installation/upgrade/security + relevant browser UX + synthetic authenticated live integration tests pass and attach sanitized evidence.
I. Operator-facing error, recovery, audit trail, help text, report and accessible navigation are demonstrated; independent domain/security review and acceptance owner sign-off recorded.

A typed form alone is only CONTRACT_CANDIDATE. Do not label it FEATURE_COMPLETE. A mocked Odoo test is not UAT. A green CI is not a deployment acceptance. If a capability truly does not apply to an agreed tenant/product, record NOT_APPLICABLE with a reason and approved scope exclusion; never silently count it as complete.

## 4. Required source-to-feature traceability matrix

Build/update docs/parity/FULL_FUNCTIONAL_MATRIX.csv or a documented deterministic equivalent generated from pinned source, with at least:
id, domain, subdomain, persona, operator_goal, Mifos menu/screen/action, pinned source path and line, Fineract endpoint/method/command, schema/fields/conditionals, required tenant/product/role, authorization and maker/checker, remote side effects/ledger, Odoo menu/model/form/flow, upstream/source gaps, error/undo/reversal paths, negative security tests, unit test, browser test, authenticated integration test, independent review reference, live UAT evidence link, status, blocker, resolution/waiver owner, accepted_at.

Statuses: NOT_MAPPED, SOURCE_MAPPED, CONTRACT_VERIFIED, IMPLEMENTED, LOCAL_TEST_PASS, STAGING_UAT_PASS, OPERATOR_ACCEPTED, NOT_APPLICABLE_APPROVED, UPSTREAM_BLOCKED, RED_APPROVAL_BLOCKED. Use machine-checkable definitions; never infer a state from an endpoint count or code directory presence. Preserve file evidence and automated summary to track both domain coverage and critical business workflows.

Enumerate every relevant screen, menu action, modal, list/detail form, submit/cancel/reverse path, role and bulk operation from the source baseline. Distinguish ALL target UI capabilities from 1,094 API contracts: one frontend task may call several APIs; one API may support many tasks.

## 5. Required functional domains (mandatory inventory and closure)

D01 Company, Fineract connection and operations administration: tenant identity/pins, offices/hierarchy, staff, users, roles, permissions, business dates, calendars/holidays, codes/config, scheduler/jobs, error/audit and setup references. Existing upstream M01 owner boundaries remain intact.

D02 Clients: search/create/edit/activate/deactivate/close, IDs, addresses, KYC, family/household, notes, documents, client transfer and status lifecycle. Support optional/tenant-defined datatables where reviewed; no arbitrary JSON.

D03 Groups/centers: membership, group/center create/activate/close, join/remove/move members, JLG/GLIM configurations, staff/officer assignment, meetings, attendance, calendar changes, transfer validations and relationship lifecycle.

D04 Lending products and individual lending: product template-driven application, approval/rejection/withdrawal, multi-tranche disbursement where source supports, disbursement-to-savings, interest/repayment details, schedule, charges, payment, waiver, refunds, undo/reversals, write-off/charge-off, recovery, closure, officer reassignment. Verify state and ledger effects remotely.

D05 Advanced lending: group/JLG/GLIM, joint liability, guarantors/co-borrowers, collateral, restructuring/rescheduling, refinance/re-age, top-ups/adjustments, foreclosure/settlement and bulk lending. Explicitly identify product/tenant-specific eligibility.

D06 Savings: product configuration, applications/approval/activation/rejection, cash deposit/withdrawal, account holds/blocking, overdraft, fees/tax, interest posting, reversals, transfers, linked accounts, closure.

D07 Fixed and recurring deposits: full lifecycle, installments, interest/maturity, partial/early withdrawal, cash modification/reversal, closure templates and settlement, with verified remote product-specific behavior.

D08 Share products: share accounts/lifecycle, purchases/redemptions, transfer/reversals where available, dividend planning and approval, allocation and payout reconciliation; do not mistake approval for paid out.

D09 Charges, standing instructions and transfers: applicable client/loan/savings charges, waive/pay/reverse, scheduled transfers, remittance integrations where source actually supports them, bounded and independently reviewed commands.

D10 Portfolio and collection operations: collection sheet preview, individual/group payments, attendance-driven collection, matching dates, bulk posting and partial failures, payment type, per-account ledger/transaction reconciliation, duplicate submissions, on-device/field collection only if part of approved MFIERP scope.

D11 Cash/branch/operational controls: cashier handoff, till/denomination, vault/bank reconciliation, end-of-day balancing where an approved Fineract-compatible operating procedure exists. Do not fabricate a new Fineract cash ledger; distinguish Odoo operational cash custody from financial posting ownership.

D12 Accounting: COA mapping and reference, accounting rules/products, journal lists, manual journal and reversal where supported, provision criteria/journal effects, period/closing procedures, trial balance/GL comparison, tenant currency and precision. Establish a source-backed mapping of Odoo operational reporting vs Fineract GL without double posting.

D13 Reports and analytics: customer/portfolio/risk/aging/collection/cash, GL/financial and audit reports, safe filtering, bounded paging, appropriate CSV/XLSX/PDF exports if genuinely required by workflows, versioned report metadata, no arbitrary unsafe SQL authoring console.

D14 Documentation, identifiers, datatables, surveys and questionnaires: registered table administration and entry forms, inline application data, protected upload/download, KYC attachments, schema evolution, answer validation and PII handling.

D15 Bulk processing and migration: schema/templates, import validation, data-quality reports, dry-run/preview/diff, office/product/GL dependency order, maker/checker approval, idempotent execution, per-row outcomes, reconciliation, replay protection, rollback/compensation plan and archived evidence. No direct core DB imports outside approved supported platform mechanisms.

D16 Audit, permissions and compliance: company+office segregation, least privilege, dual control, per-human traceability in Odoo, minimized sensitive caches, retention/erasure policy, export security, security incident/audit trail; service accounts scoped to target tenant; Fineract's own approval queue reconciled.

D17 Workflow tasks, notifications and exceptions: pending approvals, rejected and remote-pending commands, stale records, aging work, failed sync, scheduler status, maker/checker inbox, escalation, investigation and recovery views. Notifications must not misstate success.

D18 Integration surfaces: Fineract API v1/v2 only where reviewed; cross-version pins, authorized upstream MicroOps/FieldOps contracts where applicable, API error normalization, no speculative deployment or identity/finance ownership crossover.

D19 Operational UX and accessibility: operator navigation, role-based menus, dashboard, browser/mobile/tablet responsive layouts, shortcuts and keyboard focus, useful empty/loading/error states, user language and date/amount labels, consistent layout and compact interaction. This is a functional acceptance domain, not decoration.

D20 Reliability, operations and commercial release: incremental/bounded sync, checkpoints, old snapshot warnings, monitoring, rate limiting, TLS/secret rotation, provenance, backup/restore, installation/upgrade/rollback, low-resource deployment and support runbook. Confirm with target-scale synthetic load.

Domain lists describe the INVENTORY REQUIREMENT, not proof every underlying operation exists or is feasible on the deployed Fineract version. Codex must disambiguate source-supported functionality, design-only gaps, externally-owned integration surfaces and approved not-applicable exclusions in the matrix.

## 6. Standard native UI / screen flow contract

Use native Odoo 20 Community only and preserve its security model; prefer standard list/form/search/kanban/activity/wizard views over a new JS SPA.
Top-level information architecture should be task-focused, not a 942-item endpoint catalogue:
- Home / My Tasks: pending reviews, remote pending, exceptions, stale sync, today's work, source timestamps.
- Organization & Administration: connections, offices, staff/users/roles, configuration, scheduler with manager controls.
- Clients: search → client overview → KYC/identifiers → family/group links → accounts → documents → applicable action.
- Groups & Centers: member roster, meetings/attendance, collections, transfers and account context.
- Lending: loan product → application → underwriting/review → approve → disburse → repayment schedule → collect → adjust/reverse → close.
- Savings & Deposits: application → approval → deposit/withdraw → transaction and interest timeline → exception/closure.
- Shares & Transfers: lifecycle, instruction and dividend flow with audited payout status.
- Collections & Cash: daily batch/preview → validate → maker/checker → dispatch → per-account remote reconcile → close handoff.
- Accounting & Reports: finance read/verify, journals/provisioning/reporting and drilldown to remote evidence.
- Operations & Audit: command register, reconciliation queue, sync status, imports, error recovery.

Every important operation is discoverable from the relevant business record. Prepopulate only validated contextual IDs. Use reference selectors/remote options instead of free typing numeric entity IDs when a source provides choices. Explain disabled actions from state/product/role; show confirmation and exact reviewed payload for money movement. Keep desktop and mobile responsive, keyboard-accessible, low-scroll and aligned; preserve readability at 200% zoom. Avoid excessive cards, nested wizard hops, generic API identifiers and giant menus.

Screens must show organization/company/office, resource status, remote currency and last actual refresh, not fake locally calculated balances. Long-running work uses bounded progress/checkpoint and a recoverable state. No hard-coded fixture/demo data in operator production screens.

## 7. Financial safety and accounting acceptance

For EACH financial action:
- Explicit actor, role, allowed office/company, connection tenant, account/product/currency, reviewed dates and remote permission check.
- Idempotency key/correlation where supported; reviewed immutable payload digest; distinct maker/checker, no self-approval, avoid duplicate business submissions.
- Persist dispatch reservation before sending; serialize reconciliation and remote dispatch; never automatically replay timeout/unknown result.
- Distinguish local APPROVED, DISPATCHING, REMOTE_PENDING, DONE_AFTER_VERIFICATION, UNCERTAIN, REJECTED. Re-read remote accounts and ledger before declaring financial completion; no silent success on absent response fields.
- Require verified remote resource/command/transaction IDs where applicable; resource-less scheduler reconciliation is a narrow exception requiring fresh GET and independent evidence, not general permission to mark financial actions complete.
- Test undo/reversal as separate reviewed commands with causality and audit references, never transaction deletion/editing.
- Compare balance, principal, due, interest, fee, tax, GL debit/credit and transaction date per currency/product remotely. No interest/repayment accounting formulas invented in Odoo; verify COA before accounting-enabled product release.

## 8. Security and data isolation

Use Odoo 20-specific access conventions (not blindly copied Odoo 16–19 APIs); enforce security in Python AND native access policies. Implement explicit company → Fineract connection → office authorization policy with head-office and multi-office exceptions only after approved domain design. Cross-company, cross-office, cross-connection and cross-tenant attempts must be blocked on direct RPC, search, read, write, export, report and contextual actions.

Reader, Maker, Checker, Administrator roles use least privilege. Administrative changes need independent administrators when high-risk. Treat uploaded files, notes, account identifiers and logs as sensitive; enforce retention and encrypted backups as appropriate; never put secret values or customer PII in git or CI artifacts. Protect environment credentials and TLS with certificate validation. Restrict outbound network destinations to approved Fineract hosts.

Threat-test forged context defaults, stale contract digests, malicious filenames, traversal/SSRF, JSON unknown properties, insecure reports, fake source IDs, XSS, excessive pagination, SQL injection, race conditions and privilege revocation after approval.

## 9. Reliability, correctness and performance

- Replace monolithic full sync where source supports it with bounded per-resource checkpointing/incremental refresh, deterministic upsert and safe retry for reads only; preserve source-of-truth distinction and historical/deletion policy.
- Keep manual refresh for account detail; show separate portfolio-list timestamp and financial-detail timestamp.
- Use reasonable Odoo cron batching/lock scopes and back-pressure. Degraded Fineract must not block all Odoo UI and must never trigger unsafe POST replay.
- Metrics: queue by state/age, unknown result backlog, sync lag and failures by resource, failed auth/runtime drift, timeouts, request latency, stale views and operator outcomes. Include actionable operator runbook and scrubbed logs.
- Run representative synthetic scale/load and concurrency tests for target MFI size, including large portfolios and multiple branches; record measured results and capacity assumptions. Do not promise a performance threshold unsupported by evidence.
- Build, test and version on reproducible official Odoo/Fineract pins; document third-party licenses. Keep developer setup cheap and isolated; no additional Oracle long-running service without infra approval.

## 10. Codex autonomous execution work packages

WP00 BASELINE/TRACE: Freeze exact refs; inspect latest GitHub PR/CI/issues; inventory all Mifos screens/components/API calls, catalog, contracts and current Odoo screens. Build FULL_FUNCTIONAL_MATRIX with accurate statuses and prioritized dependency graph. Preserve features already written. Run baseline tests and compare coverage; publish gap heatmap and status evidence. No code changes outside MFIERP.

WP01 SAFETY CORE: Resolve P1 blockers from Issue #2, including clean Oracle runtime provenance through independent Infra handoff, read-only authentication, reconciliation edge cases, no double financial writes, security review of local command register. Keep PR draft; do not work around dirty runtime or missing credentials.

WP02 VERTICAL SLICE (Pilot GATE, NOT FINAL PROJECT): Make Client → Loan application → approve → disburse → repayment → remote balance/GL/report and Savings application → deposit/withdraw → reconciliation a compact fully native task experience. Add live option choice, status/role guidance, transaction audit, exception and reversal paths. Test mocked/local and later authorized synthetic Fineract; do not stop at pilot.

WP03 BRANCH OPERATIONS: Complete group/center/joint workflows, meetings, staff assignment, collections, cash handoff and day-close, prioritized by source and owner business requirements. Include partial failure and office security.

WP04 PRODUCTS/ADVANCED FINANCE: Loan/savings/deposit/shares/products/collateral/charges/standing instructions/provisioning/full accounting/configuration. Each feature is source-backed and carries maker/checker + read-after-write UAT.

WP05 FULL ADMIN/REPORT/MIGRATION: Complete configuration, jobs, KYC, datatables, surveys, safe reports/exports, bulk/migration templates, validation/preview/checker/reconciliation, runtime error recovery.

WP06 UX PARITY & ACCESSIBILITY: Replace generic contract-picker dependency for day-to-day tasks with standard business record screens. Test role-based navigation, keyboard, 200% desktop zoom, mobile/tablet, readability, recoverability and operational task completion.

WP07 SECURITY/PERFORMANCE/OPERABILITY: Finish Issue #3 office security and Issue #4 incremental sync, threat tests, PII minimization, large synthetic datasets, backup/restore drills, monitoring, release/upgrade migration and supporting docs.

WP08 100% ACCEPTANCE & RELEASE READINESS: Zero untriaged in-scope feature gaps; every mandatory feature in matrix OPERATOR_ACCEPTED, or a documented signed approved exclusion; authoritative domain and independent security review; matching exact-head CI; authenticated synthetic tenant UAT and remote ledger comparisons; known gap report and commercial licensing/support matrix; explicit separate owner signoff before merge, promotion or any production use.

Run WPs in dependency order but iterate within independently reversible increments. Never claim "complete" because WP numbers were executed. If a verified source behavior is unavailable, mark BLOCKED and advance only safe independent work. External approval/financial testing is not delegated by this issue.

## 11. Mandatory Codex work loop and evidence contract

For EVERY coherent increment:
1. Announce precise goal, affected domain/scope, exact repo/branch/head, evidence for source contract, risks and test plan.
2. Read AGENTS.md, this master spec, the matrix and applicable ADR/source files. Check existing issues/PRs and coordinate to avoid redundant/conflicting agent work.
3. Make a dedicated safe branch from reviewed current head if practical; work only in MFIERP; implement small changes to models + views + services + access rules + tests + docs together.
4. Verify with Python unit tests, Ruff, compilation, XML/manifest, Odoo 20 clean install, upgrade/post-install/security tests and targeted UI/browser tests using synthetic isolated fixtures.
5. Inspect exact commit SHA and exact-head GitHub CI for success; if blocked or flaky report it, do not redefine green. Repair code/test failures rather than skipping acceptance.
6. Record changed files, original source/endpoint citations, before/after functionality, security tests, commands used, outcomes and remaining blocked states in matrix/PR comment.
7. Reconcile contract drift and test evidence; do not mark live UAT from mocked calls. Keep PR Draft until independent reviewers and owner acceptance.
8. Continue next unblocked increment. Never merge/tag/deploy, access/modify production data, rotate secrets, create real customer/financial records or run staging POST without separate explicit owner approval and approved environment.

Required evidence labels: NOT_STARTED, SOURCE_VERIFIED, CODE_COMPLETE, CI_GREEN, RUNTIME_RECONCILED_STAGING, OPERATOR_VISIBLE_STAGING, UAT_PASS_STAGING, RELEASE_AUTHORIZED. These are distinct, monotonic only with valid evidence; a regression revokes the higher status.

## 12. Final "100%" release gate (ALL must be true)

[ ] Exact signed target source revisions and complete screen/action/subworkflow inventory approved.
[ ] No untriaged IN_SCOPE UI/workflow/action, contract, security, account reconciliation or report gaps; exclusions are signed NOT_APPLICABLE_APPROVED and displayed.
[ ] All critical vertical journeys pass in Odoo native UI with named role and branch controls; no Mifos Web fallback required for approved target workflows.
[ ] All financial state and ledger calculations proven Fineract-authoritative, with remote read-after-write reconciliation and negative/reversal tests.
[ ] All Mifos source gap cases (152 blocked contracts, 30 contract gaps, 25 dynamic resources, 3 unpublished routes) individually dispositioned with evidence, not necessarily forcibly enabled.
[ ] Exact-head services and Odoo clean-install/upgrade/post-install/security CI green; no critical/high defects.
[ ] Independent Odoo security and Fineract domain reviewers accepted the contracts and financial behavior.
[ ] Authorized synthetic live Fineract UAT passed, including business date/product variations, timeout/crash/replay and restore drill.
[ ] Verified company/office/tenant isolation, secret/privacy/audit controls and full money-movement approval chain.
[ ] Usable desktop/mobile workflows verified at operator scale, accessible navigation, stable errors/recovery, data freshness and monitoring.
[ ] Complete runbooks, licensing/attribution, architecture, support/migration/rollback and measurable capacity evidence.
[ ] Owner explicitly authorizes release; separate Infra/production approvals documented. No approval by assumption.

Do not claim parity or promote to production while any mandatory item is unverified.

## 13. Connected tasks and follow-up

- Draft PR #1 is the current implementation context: https://github.com/nandahtoon/MFIERP/pull/1
- Issue #2: Authorized Oracle synthetic UAT; Issue #3: office-level security; Issue #4: sync reliability.
- GitHub source repository: https://github.com/nandahtoon/Mifosx-web-app
- This specification is the one-time master instruction future Codex sessions should execute against; all work still requires evidence and safety gates. When resumed, begin at WP00 and use the matrix to find the next genuinely unblocked increment. Do not re-ask the owner to restate the already accepted architecture.

## 14. Definition of agent final reporting

Briefly report: Goal / Outcome / Files and commit / Test & CI evidence / Feature-matrix statuses / Risks & blockers / Next unblocked work. Keep reports concise in Burmese when communicating with the owner; code/docs and machine-readable evidence may be in English.
