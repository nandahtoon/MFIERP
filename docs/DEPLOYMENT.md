# Local deployment and operations

## Isolated development environment

Docker Desktop with Linux containers and Compose v2 is sufficient. The project name is `mfierp`; its PostgreSQL and Odoo volumes are separate from other applications. PostgreSQL has no host port. Odoo binds to localhost on port 18069. The addon does not start, reconfigure or write to an existing Fineract installation.

1. Copy `.env.example` to `.env` and generate a long random `MFIERP_DB_PASSWORD`. Set `MFIERP_DEFAULT_USERNAME` and `MFIERP_DEFAULT_PASSWORD` to credentials for a dedicated Fineract test tenant/service account. The `.env` file is ignored by Git.
2. Start the database: `docker compose up -d db`.
3. Initialize Odoo: `docker compose run --rm odoo odoo --database=mfierp --init=mfierp --without-demo=True --stop-after-init --no-http`.
4. Start Odoo: `docker compose up -d odoo`.
5. Open <http://localhost:18069>. On a newly initialized database, change the Odoo administrator password immediately and configure named users. The developer Compose setup is bound to localhost; do not expose it publicly as-is.
6. In Settings → Users, assign the administrator the MFIERP Administrator role, assign an Operator to the maker and a Checker to a different human user. A checker does not need maker privileges.
7. In MFIERP → Configuration → Fineract Connections, create a connection for the current company. Enter environment, HTTPS API base URL, tenant, reviewed expected version/full commit and credential prefix `MFIERP_DEFAULT`. Test and synchronize the connection. Financial dispatch is disabled by default; enable it only for an approved synthetic acceptance lane. Production connections cannot dispatch financial requests.

For the owner's existing Oracle hosting, see ORACLE-STAGING.md and `config/oracle-staging.json`.

For Fineract on the Docker host use a certificate-valid hostname reachable from the Odoo container. `localhost` inside the container is the container itself. A self-signed server requires a trusted private CA bundle; never disable certificate verification. The deployment must provide an appropriate mounted CA bundle when setting `REQUESTS_CA_BUNDLE`.

Additional connections can use distinct `MFIERP_<NAME>_USERNAME` / `MFIERP_<NAME>_PASSWORD` environment variables. Add them to your deployment configuration and restart Odoo. Connection URL, tenant and company cannot be changed after snapshots or commands exist: create a new connection instead.

Extended password/credential forms accept environment **references**, never raw credentials. Set `MFIERP_SECRET_BINDING_KEY` to a private random value of at least 32 characters. Supply dedicated `MFIERP_WORKFLOW_SECRET_<PURPOSE>` secret variables to the Odoo process using your deployment's secret manager; custom variables must be explicitly passed through the container environment. Their values are HMAC-bound when the maker submits, and resolved only immediately before the request. Rotating either the signing key or a referenced value invalidates the pending command. Review and resubmit; do not edit its payload. Back up the signing key through the protected secret-management process.

Command document bytes are stored in Odoo's protected filestore/attachments with company-bound upload records. Include the filestore in consistent backups. Finalized command file content expires after seven days; retain independent required evidence under the deployment's document-retention policy. Audit hashes and metadata remain. Unknown/pending results are not purged.

## Testing

Pure service tests and static checks:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\ruff.exe check addons tests scripts
```

Install and run Odoo tests in a separate database:

```powershell
docker compose run --rm odoo odoo --database=mfierp_test --init=mfierp --without-demo=True --test-enable --test-tags=/mfierp --stop-after-init --no-http
```

Upgrade check:

```powershell
docker compose run --rm odoo odoo --database=mfierp_test --update=mfierp --test-enable --test-tags=/mfierp --stop-after-init --no-http
```

Do not run parallel jobs against the same database. Remote financial calls are mocked in these tests. Complete the live tenant acceptance sequence in COVERAGE.md before production deployment.

The CI workflow also runs an empty-core CE uninstall check after installation and upgrade. Its explicit database/opt-in guard refuses demo/acceptance targets, any MFIERP tenant/form/attachment data and optional/dependent modules; it does not clear data to satisfy the test. Use only the isolated lane described in [EDITION_TEST_MATRIX.md](EDITION_TEST_MATRIX.md). A pass does not authorize uninstalling a populated deployment or establish licensed EE compatibility.

## Production configuration

Use a managed Odoo deployment or hardened image pinned to a tested digest, protected PostgreSQL, managed secrets, TLS ingress, restricted egress and backups. Disable public database management, set a random master password, restrict database selection and configure Odoo workers/proxy/time limits. The Compose file is a developer environment.

Enable automatic sync per connection only after manual sync succeeds. Sync needs read access to every listed resource. Dispatch starts automatically for locally approved commands; disable the scheduled action during incidents or maintenance. Limit the upstream service account's permissions and tenant/office scope.

Monitor `dispatching`, `uncertain` and `remote_pending` commands, sync timestamps/failures and cron failures. Every successful mutating response stays pending even if Fineract returns an ID. `response_received_at` records receipt, while current `completed_at` remains unset. Reconcile with independent evidence; never edit/delete command rows to clear an incident. General financial applied completion is blocked until reviewed authoritative readback verifiers exist, so this build cannot be accepted for a fully completed financial operator journey.

Back up PostgreSQL and the Odoo filestore consistently. Test restore. Before enabling dispatch after an older-backup restore, compare the command register against Fineract: disable dispatch, reconcile already applied requests, then re-enable it to avoid duplicates.

Collection preview snapshots are company-scoped and readable by operators/checkers. They are eligible for purge after seven days (100 per daily batch); hashes remain. Payment posting responses require per-account reconciliation regardless of response IDs. Changing a loaded form contract requires starting a fresh form. Preview generation is POST-based and therefore also requires independent approval, enabled staging dispatch and pinned runtime provenance.

Scheduler start/stop returns no Fineract resource ID. For those two exact declared operations, an administrator different from the maker can confirm applied state only after the adapter authenticates, checks runtime provenance and reads the expected boolean `active` value from `GET scheduler`, with independent evidence recorded. A note or resource ID cannot confirm financial/resource-bearing operations. Confirmed-not-applied also requires a different administrator and investigation evidence; it does not resend or automatically authorize a replacement. Remote maker-checker approve/reject is not enabled under the single-service-account connection profile; do not use a broad permission grant as proof of distinct remote identities.

## Upgrade to 20.0.10.0.0

Back up the isolated database and filestore consistently, disable dispatch during the controlled upgrade and run the standard module-update procedure. Upgrade validation must include representative old completed, pending and preview records before any separately approved promotion.

The upgrade deliberately reclassifies historical non-preview `done` commands to **Remote Verification Pending**, including previously manually confirmed records: the former note/ID procedure did not prove authoritative account, transaction and ledger effects. Previously pending commands with a completion timestamp stay pending and lose that timestamp only from the current-completion field. Dedicated read-only historical fields retain the prior state, completion timestamp, status message and reclassification time; payloads, IDs, maker/checker and resolution evidence are retained. Old receipt times remain unknown rather than being inferred from old completion times. Genuine collection-preview results keep their completed read result.

This can increase the pending queue without any new remote activity. It is an intentional status-compatibility change, not a reversal or a new financial action. The migration neither approves nor dispatches any command, and the worker selects only `approved`, so reclassified rows cannot be resent automatically. Do not resubmit old commands to clear the queue. Use the [outcome verification runbook](OUTCOME_VERIFICATION.md) to preserve evidence, investigate independently and track missing operation-specific verifiers. Keep Oracle/live-write authorization and release approval separate from the local upgrade test.
