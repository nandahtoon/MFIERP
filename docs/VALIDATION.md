# Validation record — updated 2026-11-20

## Proven locally

| Check | Result |
| --- | --- |
| Python service/workspace/inventory/datatable/administration/audit tests | 64 passed |
| Ruff (Python syntax, undefined/unused names, selected correctness checks) | Passed |
| Python compilation, XML parsing, manifest resources and Git whitespace checks | Passed |
| Clean Odoo 20 install and post-install ORM/workflow tests | 62 passed locally, 0 failures/errors |
| Odoo 20 upgrade and post-install ORM/workflow tests | 62 passed locally, 0 failures/errors |
| Public Oracle staging HTTPS web root and runtime config | HTTP 200 |
| Public Oracle staging health | HTTP 200, UP |
| Public Oracle staging actuator provenance | Read; observed version/full commit recorded in ignored local evidence; dirty=true |

Runtime environment: Linux `python:3.12-slim`, official Odoo source revision `c40402fab8c1509f3c68cd9cc5140f7790611d99`, PostgreSQL 18.3. The normal `odoo:20.0` image download was too slow, so validation used the official source and its Python dependency pins, with `psycopg2-binary` replacing source-built psycopg2 and optional python-ldap omitted. Relevant upstream addons and standard category manifests were fetched without modifying upstream application code. The first release also passed standard-image GitHub CI (run 44441559802). The expanded workspace passed standard-image install/upgrade plus service/static CI at commit 600c319 (run 44480659615). The secret-prefix and retention changes also passed CI at b81c717 (run 44480886662). The administrator variants also passed CI at e35702b (run 44481280391). Current 20.0.3.0.0 install/upgrade CI results are recorded in the draft PR checks.

The ORM suite verifies company isolation for searches/actions, role enforcement, self-approval rejection, immutable payloads, target connection matching, single dispatch, pre-send reservation, uncertain-result non-replay, remote maker-checker pending handling, runtime pin drift, disabled dispatch, minimized snapshots, schedule/transaction rows, typed native submission, reconciliation evidence and report HTML escaping. Remote business calls are mocked.

A queue-selection issue found during actual Odoo testing was repaired: ORM state is flushed before every SQL queue selection, ensuring completed/uncertain work is not selected again. Test assertions were retained.

Browser validation used the Playwright skill and a dedicated local Odoo demo database. Verified native navigation and client list, typed client submission into the command register, and refusal of maker self-approval. A circular company default that emptied the connection picker was found, repaired and covered by a regression test. The demo data is unmistakably synthetic. Browser screenshots and session state are local ignored artifacts.

The expanded suite verifies source-fixed commands, nested forms, transient owner isolation, protected binary capture/multipart dispatch, environment-secret binding, independent administrator review, revoked-participant denial and parent-ID-only contextual defaults. Browser checks verified catalog search/grouping, connection choice, fixed command values and nested Details editing; defects in default filtering and duplicate nested rows were repaired. Fresh standard-image installation passed. The local upgrade suite now has 30 tests, including retention of unknown outcomes, preservation of file audit hashes after byte purging, and independent administrator approval for commands without a request body. Source contracts were compiled deterministically and pinned; no live financial acceptance is implied.

## Unproven gates

- Authenticated Oracle API contract/portfolio reads: protected credentials are server-local; this workstation lacks the pinned SSH host trust required to run the existing verifier.
- Oracle synthetic loan/savings mutation, re-read, reconciliation, Show-Me/UAT and recovery drill.
- Shared Oracle deployment, infrastructure promotion, production use, cross-company office-level restriction or full Mifos X parity.
- Independent human/domain review, GitHub branch protection and release acceptance.

No business API writes, remote credential changes, Oracle runtime changes or production changes were performed. See ORACLE-STAGING.md and COVERAGE.md for the concrete next acceptance work.

Version 20.0.3.0.0 adds regression coverage for contextual loan IDs in reschedule body/query fields, reader access to request lists, one approved dispatch without implicit waivers, separate approval/rejection dates, administrator-only provisioning review, fractional charge payments and exclusive bounds. The initial local upgrade run passed all 30 ORM tests. Remote business calls remain mocked.

Browser verification for 20.0.3.0.0 confirmed the path from the synthetic loan record through More Workflows to reschedule submission, with the connection and loan ID 201 correctly populated. Nested dates, reason and optional restructuring fields rendered in the native Details form. No remote write was submitted.

Four inventory regressions verify that named routes cannot be counted as numeric ID lookups, concrete document routes still match generic entity routes, share-only contracts cannot count as loan contracts, and computed resources remain review items.

Version 20.0.4.0.0 service regressions check separate deposit collection/transaction-ID routes, rejection of undefined/zero/extra IDs, omission of source-removed fields, fixed-zero reversals and GET-only transaction templates. ORM regressions cover fractional deposit submission, independent approval, timeout non-replay, immutable reversal constants, reader template access and stale-form rejection before network access. Previous release head dbaa44b passed standard-image CI (run 44534026663); current commit verification is recorded in PR checks.

Version 20.0.5.0.0 adds source-contract tests for unique membership/transfer collections, weekly conditional fields, fixed entity types and separation of date rescheduling from recurrence changes. ORM tests exercise native array rows through independent review and POST dispatch, contextual IDs through PUT calendar dispatch, reader calendar access and rejection of unrelated entity kinds. The previous release passed standard-image CI at 564ad6c (run 44538450544); current exact-head checks are recorded on the PR.

Version 20.0.6.0.0 adds regressions for collection projection/bounds, non-empty unique payment collections, matching dates, published attendance option objects, preview escaping and role boundaries, preview expiry with retained hashes, post-response reconciliation, and malformed-reference uncertainty after sending. All 42 local Odoo tests passed; service/inventory tests passed 45 cases. Preview due/charges remain separate remote values in assertions. No live financial operation was performed.

Version 20.0.7.0.0 adds typed registered-datatable entry contracts, bounded escaped reads, single-/multi-row routes, company and role isolation, immutable metadata, stale-form and pre-dispatch metadata checks, independent administrator approval for office/product entries, contextual parent IDs and uncertain-outcome non-replay. Dispatch also locks and rechecks the reservation against reconciliation before network access. A stable source snapshot passed 51 pure Python tests, Ruff, syntax/XML/manifest checks, and 52 post-install tests on both a clean install and upgrade in a new isolated MFIERP test database using the source-based runtime described above. Remote business calls remain mocked; this does not establish live tenant acceptance.

Commit `6d733cebf818e4d94497c6d76b8b62ffb615f460` also passed the [standard-image service, clean install and upgrade CI](https://github.com/nandahtoon/MFIERP/actions/runs/44592700116). Playwright checked the registered-table menu, native table details, separate parent/entry identifiers and nested typed fields using an explicitly synthetic local fixture. No remote request was submitted during browser verification; the user's archived connection remained archived.

Version 20.0.8.0.0 adds regressions for source-fixed standing-instruction updates, explicit unique provisioning product/category collections, age-range validation, independent administrator review, dividend payout-ID capture, mandatory dividend reconciliation, and manager-only scheduler controls. All 56 pure Python tests and 56 Odoo tests passed, including clean installation and upgrade in isolated databases. Remote business requests remain mocked. Standard-image CI for the preceding datatable implementation and evidence commit also passed at 3f97ef2 (run 44593101286); current checks are recorded on the draft PR.

Playwright also verified Configuration → Scheduler Workflows and the separately listed fixed start/stop contracts in the upgraded synthetic local demo. No scheduler or other business command was submitted during this browser check.

## 20.0.8.0.1 P1 hardening (historical pre-integration checkpoint)

- Resource-less scheduler start/stop reconciliation requires a separate administrator, an evidence note and a fresh authenticated Fineract GET returning the expected `active` boolean. No remote POST is retried; other commands still require a positive verified resource ID when marked applied.
- Before any dispatch, the pinned Fineract actuator info must explicitly attest `git.dirty=false`; dirty or missing values reject the request before network mutation.
- Added mocked Odoo regressions for matching/mismatching scheduler state, independent administrator restriction and dirty/missing provenance.
- No Oracle tenant mutation or shared deployment is authorized. This original checkpoint did not establish a test pass; later integrated exact-head evidence is recorded below.

Version 20.0.9.0.0 adds typed bulk officer reassignment, body-less holiday activation, false/true savings withholding, administrator role boundaries, mandatory bulk/holiday reconciliation, scheduler status verification followed by evidence-based ID-less reconciliation, negative-ID rejection and forged-context refusal for financial commands. Remote audit reads now prove that submitted command JSON and unknown fields are excluded before persistence and cannot be obtained through binary read mode. The projection has separate shape, bounds, null and malformed-reference tests.

All 64 pure tests and 59 Odoo tests passed on both clean installation and upgrade. The final upgrade ran sequentially on an isolated test-server port after an earlier parallel test startup reported a bind collision; the final run has no such startup error. The administration implementation at e375305 also passed standard-image service, installation and upgrade CI (run 44596133585). Current exact-head checks are recorded on the draft PR. The deterministic 20.0.9.0.0 addon archive was built locally. Remote business calls remain mocked, and live Oracle financial acceptance remains outstanding.

Audit metadata projection and binary-output rejection cover both v1 audit detail/list and v2 audit pages. A registry regression checks every supported audit/checker read version; service tests now total 64.

## Integrated master-mandate baseline — 2026-11-20

The implementation was rebased onto owner mandate/ADR commit 8d4d22e and safety commit 99499d6, preserving clean-build dispatch attestation and independent fresh scheduler status verification. The scheduler regression now also rejects a fabricated positive resource ID; reconciliation uses a different administrator and an authenticated GET. The integrated baseline at [`6bf1b64dedebd0470f8d5bbb76b6b298ebebac5e`](https://github.com/nandahtoon/MFIERP/commit/6bf1b64dedebd0470f8d5bbb76b6b298ebebac5e) passed 64 tracked pure tests and 62 Odoo post-tests on both clean installation (`mfierp_test_wp00_baseline_clean`) and upgrade (`mfierp_test_expanded`). Its exact-head [standard-image CI run 44745924805](https://github.com/nandahtoon/MFIERP/actions/runs/44745924805) passed. These are CE results with mocked business calls, not EE or Oracle UAT, and they must not be transferred to a later head without its own checks.

## WP00 inventory evidence — local development increment

The source-cache and matrix helpers add 51 focused tests for canonical commit/tree identity, blob verification, archive/path defenses, atomic cache replacement, conservative source extraction, stable obligation IDs, curated evidence validation, cumulative status gates and offline tracked-artifact consistency. The complete local pure suite passed **115 tests**; Ruff passed. These checks validate inventory integrity, not the underlying operator workflow or financial outcome. The addon code is unchanged by this WP00 increment; the 62-test CE install/upgrade baseline above remains separately identified. Exact-head standard-image CI must be checked after publication.

Two canonical full-source regenerations produced identical bytes: CSV SHA-256 `31085840c41410a379c0bc71f795481992a40d6283f0c8495fb8e1c3ef499ce0` and summary SHA-256 `20656f01f8e555668cf8717a1794db4bb17d0e100db13336b9488556d4b2fa75`. The tracked consistency test runs offline in the ordinary CI suite; full source regeneration additionally needs the pinned public source cache. The generator and Git attributes retain generated evidence as LF on Windows and Linux.

The canonical Mifos source tree has 3,096 blobs. The app extractor verifies 2,863 files and 748 component screens; the separate supporting cache verifies 28 additional files, leaving 205 unselected repository blobs. The generated matrix currently records 8,062 evidence obligations: 8,047 `NOT_MAPPED`, 11 `SOURCE_MAPPED` and four `RED_APPROVAL_BLOCKED`. Forty curated rows include D01-D20/ERP requirements and explicit approval gates; no automatic extraction is promoted by API matching. The matrix does not establish an owner-approved workflow denominator or a signed exclusion. Reproduction, the provisional domain gap table and source pins are in the [parity README](parity/README.md#wp00-functional-inventory).

Core `base`/`web` dependencies and successful CE installation are separate from explicit optional-app absence/uninstall tests and licensed EE tests. CRM/Accounting adapters are not implemented, no bridge posting is enabled, and `EE_NOT_TESTED` remains. Oracle financial UAT, approved office segregation, finance ownership/bridge policy and independent acceptance remain outstanding. No new browser or live financial test pass is inferred from the source matrix.
