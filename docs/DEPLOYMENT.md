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

## Testing

Pure service tests and static checks:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\ruff.exe check addons tests scripts\build_release.py scripts\verify_staging.py
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

## Production configuration

Use a managed Odoo deployment or hardened image pinned to a tested digest, protected PostgreSQL, managed secrets, TLS ingress, restricted egress and backups. Disable public database management, set a random master password, restrict database selection and configure Odoo workers/proxy/time limits. The Compose file is a developer environment.

Enable automatic sync per connection only after manual sync succeeds. Sync needs read access to every listed resource. Dispatch starts automatically for locally approved commands; disable the scheduled action during incidents or maintenance. Limit the upstream service account's permissions and tenant/office scope.

Monitor `dispatching`, `uncertain` and `remote_pending` commands, sync timestamps/failures and cron failures. Reconcile with independent evidence; never edit/delete command rows to clear an incident.

Back up PostgreSQL and the Odoo filestore consistently. Test restore. Before enabling dispatch after an older-backup restore, compare the command register against Fineract: disable dispatch, reconcile already applied requests, then re-enable it to avoid duplicates.
