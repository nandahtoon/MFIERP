# Validation record — 2026-11-19

## Proven locally

| Check | Result |
| --- | --- |
| Python service/workspace tests | 29 passed |
| Ruff (Python syntax, undefined/unused names, selected correctness checks) | Passed |
| Python compilation, XML parsing, manifest resources and Git whitespace checks | Passed |
| Clean Odoo 20 install and post-install ORM/workflow tests | Passed GitHub standard-image CI, 0 failures/errors |
| Odoo 20 upgrade and post-install ORM/workflow tests | 27 passed locally, 0 failures/errors |
| Public Oracle staging HTTPS web root and runtime config | HTTP 200 |
| Public Oracle staging health | HTTP 200, UP |
| Public Oracle staging actuator provenance | Read; observed version/full commit recorded in ignored local evidence; dirty=true |

Runtime environment: Linux `python:3.12-slim`, official Odoo source revision `c40402fab8c1509f3c68cd9cc5140f7790611d99`, PostgreSQL 18.3. The normal `odoo:20.0` image download was too slow, so validation used the official source and its Python dependency pins, with `psycopg2-binary` replacing source-built psycopg2 and optional python-ldap omitted. Relevant upstream addons and standard category manifests were fetched without modifying upstream application code. The first release also passed standard-image GitHub CI (run 44441559802). The expanded workspace passed standard-image install/upgrade plus service/static CI at commit 600c319 (run 44480659615). The secret-prefix and retention changes also passed CI at b81c717 (run 44480886662). The subsequent administrator variants have passed local tests and require their own CI result.

The ORM suite verifies company isolation for searches/actions, role enforcement, self-approval rejection, immutable payloads, target connection matching, single dispatch, pre-send reservation, uncertain-result non-replay, remote maker-checker pending handling, runtime pin drift, disabled dispatch, minimized snapshots, schedule/transaction rows, typed native submission, reconciliation evidence and report HTML escaping. Remote business calls are mocked.

A queue-selection issue found during actual Odoo testing was repaired: ORM state is flushed before every SQL queue selection, ensuring completed/uncertain work is not selected again. Test assertions were retained.

Browser validation used the Playwright skill and a dedicated local Odoo demo database. Verified native navigation and client list, typed client submission into the command register, and refusal of maker self-approval. A circular company default that emptied the connection picker was found, repaired and covered by a regression test. The demo data is unmistakably synthetic. Browser screenshots and session state are local ignored artifacts.

The expanded suite verifies source-fixed commands, nested forms, transient owner isolation, protected binary capture/multipart dispatch, environment-secret binding, independent administrator review, revoked-participant denial and parent-ID-only contextual defaults. Browser checks verified catalog search/grouping, connection choice, fixed command values and nested Details editing; defects in default filtering and duplicate nested rows were repaired. Fresh standard-image installation passed. The final local upgrade suite has 27 tests, including retention of unknown outcomes, preservation of file audit hashes after byte purging, and independent administrator approval for commands without a request body. Source contracts were compiled deterministically and pinned; no live financial acceptance is implied.

## Unproven gates

- Authenticated Oracle API contract/portfolio reads: protected credentials are server-local; this workstation lacks the pinned SSH host trust required to run the existing verifier.
- Oracle synthetic loan/savings mutation, re-read, reconciliation, Show-Me/UAT and recovery drill.
- Shared Oracle deployment, infrastructure promotion, production use, cross-company office-level restriction or full Mifos X parity.
- Independent human/domain review, GitHub branch protection and release acceptance.

No business API writes, remote credential changes, Oracle runtime changes or production changes were performed. See ORACLE-STAGING.md and COVERAGE.md for the concrete next acceptance work.
