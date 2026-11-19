# Oracle Cloud staging integration

The owner directed this integration to the existing Oracle Cloud Mifos X hosting on 2026-11-18. MFIERP remains the integration repository. Infrastructure and runtime changes remain owned by MicroOps-Infra; the web app's source is `nandahtoon/Mifosx-web-app`.

## Discovered identity

The owner's canonical site, API URL and tenant were discovered from the connected deployment repository. Public HTTPS health, the web root, runtime config and actuator provenance were read successfully on 2026-11-18. Host-specific values are retained in the Git-ignored local `config/oracle-staging.json` profile and `.research/ORACLE-STAGING-EVIDENCE.md`, rather than published with the addon.

The tenant and environment are separate fields. An observed version/commit is not a clean-build attestation, approved image pin, financial UAT result or permission to deploy to the host. The observed build reported dirty=true; infrastructure provenance must be reviewed before runtime acceptance. MFIERP 20.0.8.0.1 now blocks mutation dispatch unless actuator git provenance explicitly attests `dirty=false` (boolean or string). A missing or dirty attestation fails closed; fix/rebuild the authorized staging runtime through MicroOps-Infra rather than bypassing this gate.

Repeat sanitized public discovery with `py scripts/verify_staging.py config/oracle-staging.json`. This tool only sends GET requests, verifies HTTPS through the default trust store, and prints status/version/commit fields rather than complete response bodies.

## Evidence sources

- [Canonical public identity](https://github.com/nandahtoon/MicroOps-Infra/blob/main/config/profiles/compact-staging-site.env)
- [Read-only integration workflow](https://github.com/nandahtoon/MicroOps-Infra/blob/main/.github/workflows/oracle-staging-integration-readonly.yml)
- [GET-only verifier and tenant contract](https://github.com/nandahtoon/MicroOps-Infra/blob/main/scripts/oracle-staging-integration-readonly.py)
- [Credential maintenance rules](https://github.com/nandahtoon/MicroOps-Infra/blob/main/docs/runbooks/STAGING-CREDENTIAL-MAINTENANCE.md)
- [Fineract-first program charter](https://github.com/nandahtoon/MicroOps-360-Fineract-Org/blob/main/docs/architecture/ops-365-project-charter.md)

The workflow uses a protected runtime environment with SSH identity and pinned known-host secret references. GitHub does not reveal secret values through its read APIs. Existing deployment verification consumes protected host-local Fineract credentials and emits sanitized status/count evidence only. Credential locations and runtime details are retained in the local evidence record.

## Current access boundary

Public HTTPS discovery succeeded. This workstation has no pinned SSH host identity for the Oracle target; strict host verification correctly refused the read-only verifier command. No trust bypass, credential rotation, runtime restart, deployment or business API write was performed. Authenticated reads and synthetic write acceptance therefore remain unverified.

An authorized operator can run the existing host-local verifier through its trusted runtime lane, or provision a scoped integration credential into the MFIERP deployment secret store. No credential should be posted in chat or copied to a public workflow/artifact.

## MFIERP connection setup

Use environment=staging, tenant=default and the profile's API URL. Keep mutation disabled. Set the reviewed expected version and full commit before the connection is used; after any snapshots/commands exist, changing those identity/pin fields requires a new connection. `Test Connection` reads actuator provenance and the offices endpoint. Before any financial POST, dispatch re-verifies live provenance against both pins and rejects production/disabled connections.

The local demo has a connection record for the discovered Oracle target with dispatch disabled and no credentials supplied. For another installation, copy `config/oracle-staging.example.json` to the ignored local profile and populate it from your approved infrastructure source.

The accepted program model keeps Odoo an adjacent ERP/integration consumer. Native Odoo screens do not change Fineract authority, replace MicroOps Web as the canonical deployed operator app, or authorize a new permanent Oracle service. This task implements the owner-requested Odoo integration locally; shared staging deployment needs its own reviewed infrastructure handoff.
