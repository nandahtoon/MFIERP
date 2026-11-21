# Architecture and decision record

## ADR 001: Native Odoo, authoritative Fineract

Accepted by the project owner on 2026-11-18. Native Odoo screens replace the operator UI for the supported workflows. Apache Fineract remains responsible for financial calculations, business date, account lifecycle validation, balances, interest, repayment allocation, charges and its ledger. No Angular iframe, browser credential handoff, direct database integration or duplicated interest engine is used.

Odoo is authoritative for integration configuration, maker/checker identity, immutable command payloads, local approval decisions and reconciliation evidence. Fineract is authoritative for remote outcomes. A locally approved command is not a completed transaction. A successful command response is not a refreshed balance. Runtime dispatch additionally requires an explicit clean-build attestation from `git.dirty=false`; a pinned commit without this evidence is insufficient.

## Data flow

1. A company-scoped connection reads service credentials from environment variables.
2. Bounded, ordered GET requests synchronize portfolio/reference records. Unique `(backend, kind, remote_id)` keys prevent duplicate mirrors.
3. Operators enter data in a typed native form. Related records must match the connection and resource type; arbitrary API payloads/routes are unavailable.
4. Submission creates an immutable command containing the maker, payload, SHA-256 digest and UUID idempotency key.
   Create commands without an operator-provided external reference receive `MFIERP-<UUID>` before review, preserving a stable remote correlation reference for that submission.
5. A different checker reviews the exact payload and approves or rejects it. A row lock serializes competing approval actions.
6. The cron worker selects approved commands using `FOR UPDATE SKIP LOCKED`. It persists `dispatching` through Odoo's cron transaction API before any remote POST.
7. Dispatch validates the digest and registry schema, then sends one POST. There are no automatic POST retries. The remote idempotency header is additional protection; it is not assumed to be supported by every Fineract version.
8. A returned response records `response_received_at` and remote resource/command IDs without retaining response bodies. Every successful mutating response remains `remote_pending`, with `completed_at` unset, even when a resource ID is present. A remote command ID can represent Fineract-side maker/checker work; neither identifier proves account, transaction or ledger effects. The separately declared collection preview is a POST-based read and may finish as `done` with its bounded preview digest; it does not post payments.
9. Transport failures, malformed successful responses and server failures require reconciliation. A crash leaves `dispatching` persisted. Reconciliation requires an administrator different from the maker for either outcome and never resends a request. A manual note or positive ID cannot mark a financial/resource operation applied: no authoritative financial readback verifier is implemented. Only the exact source-declared scheduler start/stop contracts may reach applied completion, after a fresh authenticated, runtime-pinned GET confirms the expected boolean state and independent evidence is recorded. A matching scheduler state verifies an end state, not causal proof that a particular POST ran. Confirmed-not-applied remains a manual independent investigation decision; it is not an automated proof or permission to resend.

## Transaction boundary

Odoo cannot atomically commit its database and an HTTP transaction in Fineract. The durable sending barrier intentionally chooses manual reconciliation over duplicate financial requests. The only explicit transaction completion API used is `ir.cron._commit_progress`, inside a cron callback. A database rollback after remote success leaves the earlier dispatch reservation intact.

After the durable reservation, dispatch locks the command again and rechecks its state before network access. The lock remains held through response persistence, serializing dispatch with reconciliation. A reconciliation that wins the reservation-to-dispatch gap prevents the later worker from sending.

A replacement command must only be considered after an independently confirmed non-application or definitive pre-send/rejection outcome, under the approved operating procedure. A new command requires its own maker/checker review. Different submissions have different keys: business duplicates are not automatically detected. Fineract's own maker checker and permissions remain in force and require a remote operating procedure.

Version `20.0.10.0.0` intentionally changes historical success presentation. On upgrade, old non-preview `done` commands become `remote_pending`, and old pending commands with a completion timestamp remain pending with that timestamp removed from current completion. Prior state, completion timestamp and status message are retained in dedicated historical fields; resource IDs, payloads, maker/checker and resolution evidence remain. No response-receipt timestamp is invented for old records, and no request is requeued. Genuine preview results retain their completed preview state. See [outcome verification](OUTCOME_VERIFICATION.md) for the operator impact and remaining verifier obligations.

## Security boundaries

- Four roles: Reader, Operator/Maker, Checker, Administrator. Administrators have maker and checker capabilities, but cannot approve their own commands.
- Odoo 20 `ir.access` global domains restrict every persistent tenant model to allowed companies. Mirrors and commands have no direct user create/update/delete grants; Python also rejects direct mutations.
- Narrow private methods use `sudo()` to persist snapshots and workflow transitions only after public methods verify role, record access and relationships.
- Private methods are not callable through Odoo RPC. Context values cannot grant synchronization or command-write privileges.
- HTTPS certificate verification is always enabled; redirects are disabled. The API URL has a fixed path and contains no credentials. Use `REQUESTS_CA_BUNDLE` to trust a private CA.
- Only administrators can configure remote URLs and environment credential prefixes. These are trusted deployment administrators; network egress policy should limit them to authorized Fineract hosts.
- Service credentials are per connection, not per human. Fineract's audit user is the service account; Odoo retains the human maker/checker IDs. Use separate service accounts and tenants to match the desired company boundary.
- Read access covers the company's full synchronized portfolio. Office-level restrictions and per-human remote identity propagation are not implemented.
- Snapshots and command payloads can contain personal information. Apply the organization's backup, encryption, retention and authorized-export policies. No HTTP response bodies or credential values are logged by the adapter.

## Data interpretation

Portfolio list refresh and financial detail refresh are distinct timestamps. Only detail/summary responses update financial amounts. Transaction and schedule rows are replaced on account detail refresh. A synchronized list does not prove that its older detail rows are current. Amounts are displayed in their remote currency with six fractional places; there are no cross-currency totals or local financial calculations. A purpose-specific JSON projection preserves required upstream fields for administrators; arbitrary associations, identity documents and unneeded response attributes are not copied into it.

The projection exists to support native searchable Odoo lists and account detail views without an HTTP request per cell, not to become a mutable operational master. The integration administrator owns cache access and refresh. Commands preserve reviewed request/audit data; snapshots have a different retention purpose. Deployment acceptance must define cache retention/deletion and command audit retention according to the organization's policies. No production PII retention policy is assumed by this development release.

Sync preserves historical records absent from a later response; it does not infer deletions. Use timestamps and remote detail refresh to distinguish stale snapshots. The first list response may omit summaries: financial amounts are unverified until a financial-detail timestamp exists.

## Odoo version policy

This module targets Odoo 20 Community and licensed Enterprise, Python 3.12+, PostgreSQL 16+; actual runtime evidence remains CE only. Odoo 19 was reviewed as a migration reference, not declared compatible. Odoo 20 replaces `ir.model.access`/`ir.rule` with `ir.access`, uses `res.groups.privilege`, and uses `group_ids` on users. Backporting requires a separate 19.0 branch, security conversion and independent installation tests. Native list/form/search views avoid an Angular or custom JavaScript runtime dependency.


## ADR 002 — edition-neutral core and optional CRM/Accounting integrations

The owner subsequently required BOTH Odoo 20 Community and Enterprise compatibility with native CRM and Accounting integration. [ADR 002](ODOO_20_EDITION_CRM_ACCOUNTING_ADR.md) is the detailed design amendment. The current manifest is edition-neutral but native CRM/account crosswalk/bridge modules have NOT yet been implemented, and Enterprise is not yet tested. Fineract remains authoritative for the microfinance subledger and financial events; Odoo can independently account for its own ERP-originated expenses/invoices. A signed, isolated, OFF-by-default summarized journal bridge may map verified Fineract accounting batches to the ERP consolidated GL without duplicate per-loan posting. The general ban on duplicating/recalculating the Fineract financial engine still applies.

## Remote maker-checker identity boundary

Local maker/checker identities and Fineract service identities are distinct controls. Remote approval remains unavailable under the current single-service-identity profile. The reviewed Fineract same-user restriction has configuration and checker-superuser exceptions; broad permission must not substitute for remote identity separation. A future remote decision adapter requires environment-only checker credentials, verified authenticated numeric identity, original-audit maker binding and an independently enforced unequal remote checker ID. It must recheck the pending audit before dispatch and must never automatically finalize an earlier local command.

Scheduler start/stop has a narrowly declared resource-less reconciliation path: independently verified fresh status and evidence can confirm it without a remote ID. Other operations require a reviewed authoritative readback verifier before applied completion; supplying a positive ID is insufficient, and no general verifier exists yet. Client context cannot broaden the exception.

Remote audit and pending-checker reads are administrator-only metadata views. Their projection retains declared audit identifiers, actor/status/timestamp information and resource references, with a 200-row bound. It excludes submitted command JSON, unknown fields, URLs/IP addresses and nested payloads before any result is stored. Raw binary reads are unavailable for those contracts. This preserves useful reconciliation references without copying potentially credential-bearing remote commands into Odoo.
