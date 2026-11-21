# Mifos X parity evidence

The extended workspace contains **1,097 contracts**: 966 HTTP operations from the Oracle-hosted public Fineract OpenAPI definition, plus 108 separately source-reviewed command variants and 23 reviewed forms without a command parameter. **945 have typed forms; 152 remain blocked**. A form's availability is not proof of operator workflow parity, API correctness in every tenant configuration, or live acceptance.

The public API snapshot identifies Fineract 1.16.0-SNAPSHOT. Its canonicalized SHA-256 and component schemas are embedded in `addons/mfierp/services/catalog.json`. No host address, service credential or business observations are included. Apache metadata attribution and license accompany the catalog.

## Source comparison

The [machine-readable inventory](mifos-endpoints.json) compares 720 literal HTTP calls from 99 Mifos service/routing source files against the catalog. Source revision: `nandahtoon/Mifosx-web-app@34c7f278861ef25052f2e00d106d8527f5d270d3`. Each call has a source link and line number. Another 180 action components were collected; selected submit handlers were inspected to verify command names and payload transformations.

| Inventory status | Calls | Meaning |
| --- | ---: | --- |
| TYPED_CONTRACT_CANDIDATE | 666 | Compatible method/path and at least one typed candidate; command selection and complete workflow still require verification |
| CONTRACT_REQUIRES_SOURCE_WORK | 26 | Matching API metadata exists but no usable typed candidate |
| DYNAMIC_RESOURCE_REQUIRES_REVIEW | 25 | Resource itself is computed by the frontend; matching route templates alone are insufficient |
| NOT_IN_DEPLOYED_OPENAPI | 3 | No compatible published operation; investigate service ownership and deployment |

The inventory is intentionally conservative about verification: every `operator_workflow_verified` and `live_uat_verified` flag remains false. Matching ignores query strings and does not prove command or payload equivalence. Literal source segments must fit declared path parameter types/enums: a preview name cannot be counted as a numeric transaction lookup. This correction reduces false typed candidates; it does not remove a working addon feature. Multiple frontend calls can share one backend operation, and one computed call can represent many workflows. These counts are not a percentage of product completion.

## WP00 functional inventory

The [full functional matrix](FULL_FUNCTIONAL_MATRIX.csv), [generated summary](FULL_FUNCTIONAL_MATRIX.summary.json), [curated workflow evidence](CURATED_WORKFLOWS.json) and [work package plan](WORK_PACKAGE_PLAN.md) establish a reproducible review baseline for [master issue #5](https://github.com/nandahtoon/MFIERP/issues/5) and [ERP issue #6](https://github.com/nandahtoon/MFIERP/issues/6). The matrix has 49 columns covering source facts, contract candidates, native context, permissions, financial effects, negative/reversal paths, edition evidence, tests and acceptance. It is an inventory of evidence obligations, not an approved count of distinct business features.

At the pinned source revision, the extractor verifies 2,863 application files: 1,373 TypeScript, 743 HTML and 747 SCSS files. It finds 748 component screens, 745 templates (including two inline templates), template events/navigation, dialog actions, routes, switch branches, HTTP obligations and explicit review gaps. Forty-one upstream source spec files are hash-verified but excluded from operator action extraction; their existence is not Odoo test evidence. Cross-file aliases, computed targets, rendered Angular control flow, feature flags and business permissions still need semantic review. A directory-derived domain is provisional, and an API candidate never promotes a row to implementation or acceptance.

The 8,063 rows comprise 8,022 automatic extraction obligations and 41 curated rows. Every automatic row remains `NOT_MAPPED`. The curated input adds 25 broad D01-D20/ERP requirements, one mapped WP01 outcome-verification requirement, 11 source-reviewed workflows and four external approval gates. Total states are **8,047 `NOT_MAPPED`, 12 `SOURCE_MAPPED`, four `RED_APPROVAL_BLOCKED`**. There are no `OPERATOR_ACCEPTED`, `STAGING_UAT_PASS` or approved exclusion rows. The reviewed workflows and safety requirement link existing native building blocks without claiming complete task UX, office segregation or financial UAT.

The following gap table is a triage view of provisional domain assignments. Counts include screens, handlers, route branches and review obligations that can overlap within one workflow; they must not be summed into a feature denominator. All domains still require source semantics, native operator journeys and acceptance evidence.

| Domain | NOT_MAPPED | SOURCE_MAPPED | Approval gates | Next review focus |
| --- | ---: | ---: | ---: | --- |
| D01 Organization/admin | 1,410 | 2 | 0 | Hierarchy, setup and scheduler conditions |
| D02 Clients/KYC | 503 | 0 | 0 | Identity, lifecycle, KYC and exception paths |
| D03 Groups/centers | 430 | 0 | 0 | Membership, joint workflows and meetings |
| D04 Individual loans/products | 969 | 1 | 0 | Complete lifecycle, reversals and readback |
| D05 Advanced lending | 247 | 0 | 0 | Restructure, guarantors and computed targets |
| D06 Savings | 488 | 1 | 0 | Cash, tax, holds, closure and readback |
| D07 Deposits | 661 | 0 | 0 | Maturity/settlement and product conditions |
| D08 Shares/dividends | 519 | 2 | 0 | Approval versus allocation/payout evidence |
| D09 Charges/transfers | 274 | 0 | 0 | Charge/instruction/transfer lifecycle |
| D10 Collections | 28 | 0 | 0 | Group/batch behavior and per-account evidence |
| D11 Cash/branch | 85 | 0 | 0 | Cash custody and approved ledger ownership |
| D12 Accounting/GL | 485 | 2 | 1 | GL comparison, period controls and bridge policy |
| D13 Reports | 146 | 0 | 0 | Filters, export, tenant options and source totals |
| D14 Documents/datatables/surveys | 207 | 2 | 0 | Schema/inline forms, survey and privacy paths |
| D15 Bulk/migration | 22 | 0 | 0 | Computed import targets, preview and row outcomes |
| D16 Audit/permissions | 67 | 2 | 1 | Office policy, remote checker identity and privacy |
| D17 Tasks/recovery | 114 | 0 | 0 | Exceptions, uncertainty and operator recovery |
| D18 Integration | 12 | 0 | 1 | Clean runtime, version selectors and source flags |
| D19 UX/accessibility | 1,378 | 0 | 0 | Shared controls, navigation, language and role UX |
| D20 Reliability/editions | 2 | 0 | 1 | Sync/operations and licensed EE evidence |

The separate gates are Oracle clean-runtime/synthetic-UAT handoff, approved office policy, licensed EE testing and signed GL ownership/bridge policy. Required approval roles in a row are unassigned requirements, not named approvers or signatures. CE CI is independent of EE (`EE_NOT_TESTED`); no source feature is silently excluded because a feature flag is off in one environment. Continue local WP01 safety work and bounded source triage while external gates remain closed.

### Reproduce the source and matrix

Use the public pinned source only; the cache is reference material and is never executed. The helper fetches the commit-to-tree relationship and complete recursive tree, rejects truncated or tampered trees, verifies Git blob hashes before replacing a cache and writes an ignored `.source-lock.json`.

```text
python scripts/fetch_mifos_source.py .research/mifos-repository-tree.json .research/mifos-full-34c7f27 --revision 34c7f278861ef25052f2e00d106d8527f5d270d3 --scope app --fetch-tree
python scripts/fetch_mifos_source.py .research/mifos-repository-tree.json .research/mifos-supporting-34c7f27 --revision 34c7f278861ef25052f2e00d106d8527f5d270d3 --scope supporting
python scripts/build_functional_matrix.py --source-root .research/mifos-full-34c7f27 --tree .research/mifos-repository-tree.json --endpoints docs/parity/mifos-endpoints.json --catalog addons/mfierp/services/catalog.json --curated docs/parity/CURATED_WORKFLOWS.json --output docs/parity/FULL_FUNCTIONAL_MATRIX.csv --summary docs/parity/FULL_FUNCTIONAL_MATRIX.summary.json
```

The commit points to Git root tree `559162e9aeb0903a7909752ec8f1e513827f105f`: 3,998 tree entries and 3,096 blobs. The reviewed archive SHA-256 is `2b826fd596c39e5e8a5cddba6a25342884079fd22acbeee441a9bf0b5722b660`. Application extraction selects 2,863 blobs, leaving 233 outside its extraction scope. The separate supporting selection verifies 28 files (governance, environment/configuration, translations and the app error-handler README), so the combined selected caches contain 2,891 files; 205 repository blobs remain explicitly unselected. Full repository tree verification does not mean all repository assets have been semantically reviewed or extracted as operator features. Selection rules and excluded scope are recorded by the helper and matrix manifests.

The canonical matrix manifest identifies `CANONICAL_COMPLETE_REPOSITORY_TREE`, a verified root tree identity and the app-only extraction boundary. Legacy app blob lists are accepted only as `LEGACY_APP_BLOB_LIST_UNVERIFIED_ROOT`, with no verified root-tree claim; use the canonical input above for published reproduction. Curated source mappings are explicit tracked input. Higher statuses require cumulative evidence, and placeholders such as `EE_NOT_TESTED` cannot satisfy a test gate. Deterministic regeneration, schema/source-link/status validation and focused extractor/cache tests are separate from Odoo workflow and live UAT evidence.

## Separately reviewed variants

`scripts/command_contracts.py`, `scripts/admin_contracts.py` and `scripts/organization_contracts.py` declare 108 fixed commands, reviewed against pinned frontend handlers and relevant Fineract implementations. The compiled entries include their source links. They cover client activation/reactivation/closure/rejection/withdrawal/staff assignment/savings linkage/transfers; loan approval/rejection/withdrawal/disbursement to savings/officer assignment/reversals/closure/waiver/recovery/charge-off; savings lifecycle/officer changes; fixed and recurring deposit approval/rejection/withdrawal/closure; savings holds/blocking/as-of interest; group and center activation/closure; group staff assignment; shares activation/approval/rejection/closure/purchase/redemption/reversal; manager-only role enable/disable, survey activation/deactivation and job execution without custom parameters; loan reschedule submission/approval/rejection/pending reads; charge payment/waiver/inactivation; provisioning journal generation/recreation; standing-instruction updates; dividend approval; and scheduler start/stop.

Each variant exposes exactly one command value. The unresolved parent operation remains visible as a gap; no generic command textbox can bypass it. Loan-product fee/penalty accounting mappings are narrowed to source-confirmed charge/account IDs, avoiding recursive response projections. Java DateParam and MIME wrapper schemas are normalized to their actual wire types. Six v2 operations use the same configured host and tenant with a fixed version selector. Manual Fineract journal creation uses its typed default POST contract without a free-form command. A separate loan application contract permits declared borrower/product fields and explicitly excludes tenant-defined datatables; its unresolved generic parent remains blocked.

## Remaining work

- Review the 152 blocked contracts: multiplexed commands, opaque or tenant-defined data objects, unsupported body encodings, authentication/session integrations and non-API metadata endpoints.
- Complete dedicated workflows for datatable schema administration and inline application data, surveys/questionnaires, collection sheets, complex group/JLG/GLIM/GSIM lending, re-age/refinance and full rescheduling acceptance, advanced deposit settlement, bulk processing, report authoring and external integrations. Some underlying typed operations are already accessible; complete screen behavior remains unverified.
- Add product/template-driven option selection, contextual navigation and business-date/currency presentation across every extended form. Current ID/enum fields follow the pinned API types and rely on remote validation.
- Define office-level user scoping with the deployment owner. Company boundaries do not imply office boundaries.
- Run synthetic end-to-end acceptance on the intended Oracle tenant, including file handling, administrator actions, failure outcomes, remote maker/checker, reconciliation and recovery. Server-local credentials and SSH host trust are still unavailable here.
- Obtain independent Odoo/security and Fineract/domain review before release acceptance.

## Reproduce

Compile an explicitly supplied public API definition, then compare the source-derived call inventory:

```text
python scripts/build_capability_catalog.py PUBLIC_OPENAPI_JSON addons/mfierp/services/catalog.json
python scripts/inventory_mifos_parity.py SOURCE_HTTP_CALLS_JSON addons/mfierp/services/catalog.json docs/parity/mifos-endpoints.json --repo nandahtoon/Mifosx-web-app --revision 34c7f278861ef25052f2e00d106d8527f5d270d3
```

The research cache is ignored and contains upstream reference source, not addon dependencies. Updating a compiled contract changes its digest and invalidates pending workspace requests; review and resubmit affected work rather than editing audit rows.

## Rescheduling and charges in 20.0.3.0.0

Loan records now link to the source-reviewed reschedule submission and request-list forms. The server supplies the current loan ID to the declared body/query field; approval/rejection use the separate reschedule request ID and distinct date contracts. Operations also has a Loan Rescheduling menu. No penalty waiver runs implicitly alongside a reschedule request. Submit waivers separately, confirm their outcomes, then review the reschedule. Fineract calculates all schedules.

Client and savings charge payments support fractional amounts and require a strictly positive amount. Savings waiver/inactivation use fixed empty-body commands. Provisioning journal generation/recreation require a maker and an independent checker who both have the administrator role. Provisioning Workflows is available under Accounting and Reports to administrators. No Odoo ledger entries are created.

The validation engine now enforces both boolean OpenAPI and numeric JSON Schema exclusive bounds. Source links are embedded in the new contract variants. Mifos references include loan-reschedule.component.ts, reschedule-loan-tab.component.ts, tasks.service.ts, client-pay-charges.component.ts, savings view-charge.component.ts, apply-annual-fees-savings-account.component.ts, and accounting.service.ts at the pinned revision above.

## Fixed and recurring deposits in 20.0.4.0.0

Portfolio → Deposit Workflows groups account reads and native forms for applications, lifecycle, cash transactions, adjustment/reversal and closure. Sixteen additional fixed-command contracts cover activation, undo approval, deposit/withdrawal, modification/reversal, closure templates and recurring deposit transaction templates. The existing lifecycle and application forms remain available.

The pinned Mifos fixed-deposit cash component calls a helper whose optional transaction ID can be undefined. MFIERP uses the new-transaction collection route from the published API and corroborating Fineract source; only modifications/reversals accept an existing transaction ID. Cash forms omit the note field removed by the source submit handler. Reversal amounts are fixed to zero and cannot be changed through RPC. Required payment type selection follows the recurring-deposit source form. All writes use independent approval and uncertain results are never replayed automatically.

Backend source reviewed at `apache/fineract@6a28754c6839fa64f5faf1873f9fcb52bc330fd9`: `portfolio/savings/api/FixedDepositAccountTransactionsApiResource.java`, `RecurringDepositAccountTransactionsApiResource.java`, `FixedDepositAccountsApiResource.java`, and `RecurringDepositAccountsApiResource.java` under `fineract-provider/src/main/java/org/apache/fineract/`. Their links are embedded in the compiled variants. This source review and published metadata do not establish authenticated compatibility with the Oracle tenant.

Open forms now pin the compiled contract when their fields are loaded. A catalog change rejects stale forms before a read or submission; open a fresh form and review the values. Pending commands retain the existing immutable contract-digest check.

## Groups, centers and calendars in 20.0.5.0.0

Five fixed-command variants support client association/disassociation, center group association/disassociation and client transfer between groups. Member collections contain positive integer IDs; transfer collections contain objects with only an id. Collections are non-empty, unique and limited to 100 rows. Inheritance of the destination loan officer is an explicit choice; Fineract controls active-loan transfer defaults. Review the affected accounts before approval.

Ten additional non-command forms cover scoped group/center calendar reads, repeating meeting creation/editing, date rescheduling and default group/center templates. Entity types are fixed per form. Record context fills only the parent entity ID; the separate calendar ID is entered explicitly. Weekly recurrence requires a weekday. Date rescheduling cannot smuggle recurrence changes. Meeting titles are supplied explicitly. Repeating collection meetings are the specialized scope; general one-off calendars, attendance and live acceptance remain separate work.

Mifos source references at the pinned revision: manage-group-members.component.ts, manage-groups.component.ts, group-transfer-clients.component.ts and its HTML option values, attach/edit group/center meeting components and the meeting-schedule components. Apache GroupsApiResource.java corroborates group transfer behavior; CalendarsApiResource.java corroborates scoped calendar routes. These classes were reviewed at the Apache revision recorded above. No recurrence or repayment calculations were copied into Odoo.

Validation also checks that a workflow bound to a group cannot carry a loan/center record as its context. All membership and calendar writes retain independent approval, immutable payloads, runtime provenance checks and non-replay of unknown outcomes.

## Attendance and individual collections in 20.0.6.0.0

Six scoped attendance forms expose group/center templates, meeting lists and attendance submission. The pinned frontend sends scalar attendance types, while published metadata and the reviewed Java MeetingCreateRequest/MeetingAttendanceData DTOs require an EnumOptionData object. MFIERP follows the published object shape (required id, optional code/value) and rejects duplicate client IDs. The frontend calenderId query typo is omitted; the authoritative calendarId field is sent in the body or declared query. Authenticated acceptance of this normalization is still required.

Individual collection generation is a POST-based read in the reviewed CollectionSheetApiResource. It remains independently approved and uses the same dispatch gates. Its bounded projection contains up to 200 clients/500 account rows, remote due and charge amounts, product/client labels and payment type options. No totals or rounding from the frontend are copied. Extra response fields are discarded and HTML is escaped. Preview data is eligible for purge after seven days in bounded daily batches, retaining its digest and audit references.

Collection posting is a separate immutable command. Only explicit positive loan repayments and savings/recurring dues (100/300) are supported. Empty collections, duplicate account IDs and mismatched transaction/disbursement dates are rejected. Even successful responses with IDs remain pending verification until every affected account/transaction is reconciled. There is no automatic preview-to-post chain or uncertain-result retry. Joint-liability collection sheets and bulk disbursements remain separate work.

Malformed references or response-processing errors after network dispatch now become uncertain rather than pre-send failures. This preserves the sending barrier and avoids treating a possibly applied request as safe to repeat.

## Registered datatable entries in 20.0.7.0.0

An administrator discovers registrations from the selected connection. A separate server-side adapter validates supported application tables, primary/parent keys, column identifiers, explicit nullability and dropdown IDs before generating typed entry forms. Unknown types and credential-bearing columns remain blocked. Single-row forms use the parent route; multi-row update/delete forms additionally require an explicit entry ID. Reads request the generic result set and retain only declared columns in a bounded escaped preview.

Forms and immutable commands pin the connection, company, action and normalized metadata digest. Remote metadata is checked immediately before reads and writes. Every write retains independent approval, runtime checks and unknown-outcome reconciliation; office/product entry writes require two different administrators. Portfolio record navigation filters the connection/application and prefills the parent ID while leaving multi-row entry IDs explicit. These runtime-derived forms do not change the static catalog counts or the inventory's unverified workflow/UAT flags. Table creation, registration changes, SQL/query consoles, inline loan-application data and full tenant acceptance remain separate work.

## Standing instructions and administration in 20.0.8.0.0

Seven new reviewed contracts cover standing-instruction updates, provisioning criteria creation/editing, dividend plan creation/approval and scheduler start/stop. Standing instructions retain fixed commands and declared recurrence/date fields. Provisioning uses explicit unique product/category rows and remote ledger account IDs; it does not silently select all products or calculate provisions. Scheduler reads and writes require administrators, and commands require a distinct administrator checker.

Dividend creation retains Fineract's payout subresource ID. Both creation and approval require reconciliation of the remote plan and affected accounts; an approval response does not prove that payouts occurred. The reviewed Fineract approval service does not consume body values, so the native approval contract submits an empty object rather than duplicate editable IDs. The original unresolved command operation remains blocked. All inventory workflow/UAT flags remain unverified.

## Organization operations in 20.0.9.0.0

Three contracts add explicit bounded loan-officer reassignment, holiday activation and boolean savings tax withholding. Source/destination officers must differ; bulk loan IDs are unique and non-empty. Bulk assignment and holiday activation remain pending verification of affected remote resources after their responses. Holiday administration and bulk assignment require two administrators. No office ID, arbitrary loan object or holiday body can be injected into these specialized contracts.

A source-declared exception permits scheduler start/stop confirmation from independent status/audit evidence without a fabricated resource ID. It does not extend to financial or resource-bearing operations. Context flags cannot grant the exception.

Remote maker-checker approve/reject remains blocked pending a separate verified checker identity. At the reviewed Fineract source, same-maker checks can be bypassed by checker-superuser permissions, including ALL_FUNCTIONS. Two local approvals do not establish two distinct remote principals. A future adapter must authenticate the remote checker, bind the selected audit to its original numeric maker ID, enforce inequality independently, recheck pending state before dispatch and retain manual reconciliation afterward. It must not automatically complete a parent local command.

## Outcome controls in 20.0.10.0.0

Every mutating response stays pending verification, including resource-ID responses. Receipt and completion timestamps are separate. Applied reconciliation is blocked for financial/resource workflows until a reviewed authoritative verifier exists; ID/note/context alone cannot confirm completion. Only the exact scheduler status verifier and the non-posting preview have the existing narrow completion paths. A different administrator must investigate either manual outcome; confirmed-not-applied never resends a command. Historical response-based confirmations and pending completion timestamps are preserved separately during upgrade. The new `CURATED-REQ-WP01-OUTCOME` row records this safety work at `SOURCE_MAPPED`, with no financial, browser, edition or UAT acceptance promotion. See [the verification runbook](../OUTCOME_VERIFICATION.md).
