# Governance and contribution rules

MFIERP is the integration source of truth. The initial upstream commit contained only `README.md`; this release establishes the project conventions rather than claiming to inherit a pre-existing governance framework.

The existing OPS-365 program charter, Fineract-first direction and MicroOps-Infra deployment rules were subsequently reviewed through GitHub at the owner's direction. MFIERP adopts their API-only authority boundary, explicit environment/tenant separation, synthetic staging requirement, exact runtime provenance, unknown-outcome reconciliation and evidence-based completion vocabulary. Source rules for other repositories do not transfer their implementation ownership to MFIERP. See ORACLE-STAGING.md for the concrete discovered runtime and current access boundary.

Use `CODE_COMPLETE`, `CI_GREEN`, `RUNTIME_RECONCILED_STAGING`, `OPERATOR_VISIBLE_STAGING` or `UAT_PASS_STAGING` only when their evidence exists. A local UI or successful unit test does not establish staging acceptance. No Oracle runtime service, credential, business data or deployment change is authorized merely by creating this addon.

## Change process

Use a feature branch and a pull request describing the operator behavior, endpoint contract, permission changes, failure handling and tests. Financial contract changes need review by a Fineract/domain reviewer and an Odoo/security reviewer. The repository owner assigns actual reviewers and branch protection; documentation does not configure GitHub protections automatically.

Before accepting a change:

- Update the feature coverage and source provenance documents.
- Add registry schema and typed form fields together. No free-form API command consoles.
- Test unauthorized RPC, cross-company/connection references, self approval, invalid payloads and uncertain dispatch outcomes.
- Run static checks, pure service tests and Odoo 20 install/upgrade plus post-install tests.
- Review money movement with tenant product rules, business date, currency precision and Fineract-side maker checker enabled as appropriate.
- Verify the complete workflow in a dedicated non-production Fineract tenant before release.

## Coding conventions

Follow upstream Odoo naming, import ordering, translation and extension patterns. Use model-prefixed Python files, `action_` public methods, `_` private helpers, explicit constraints and modern XML modifiers. Keep adapter code independent of the ORM so network behavior can be tested without Odoo. Follow Fineract's public API and Mifos X's endpoint usage; never scrape the Mifos UI or read its backend database.

No manual `cr.commit()` in business code. Cron dispatch uses the documented transaction-aware cron API for a durable pre-send barrier. SQL is limited to parameterized row locks/queue selection; permission checks precede locks initiated by users.

## Releases and support

Use Odoo addon version `20.0.major.minor.patch`. Record tested Odoo and Fineract versions separately from reviewed source versions. Do not label mocked contract tests as live financial integration tests. A release needs a backup/restore drill, a reconciliation drill and a staging acceptance record before production use.

Avoid broad automated dependency upgrades to financial API contracts. Review upstream changes, update the provenance lock, test migration paths and retain compatibility notes. Never enable automatic retries of unknown financial outcomes.

## Incident handling

Disable the dispatch scheduled action before investigating duplicate or uncertain commands. Preserve the command register, remote command IDs, payload hashes and independent Fineract evidence. Reconcile against remote audit/transactions before submitting replacements. Do not edit command rows or delete audit data to clear an incident.

Credential exposure: rotate the remote service account secret, replace deployment environment values, restart Odoo, and review Fineract and Odoo audit activity. Do not include secrets or personal information in public GitHub issues.
