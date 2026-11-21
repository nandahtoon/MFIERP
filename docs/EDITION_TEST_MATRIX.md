# Edition and optional-app evidence

The owner requires Odoo 20 Community and licensed Enterprise, with independently installable CRM and Accounting adapters. The core remains `base`/`web` only. The table records observed evidence; a source manifest or CE pass cannot establish an Enterprise pass or complete operator parity.

| Lane | Observed result | Remaining acceptance |
| --- | --- | --- |
| CE core clean installation and upgrade | 65 mocked ORM/security/workflow tests passed locally; exact-head WP01 [CI 44872662076](https://github.com/nandahtoon/MFIERP/actions/runs/44872662076) passed at `9afffb90b274a19fa78bfceb0942039f6fd4778e` | Full source-mapped operator/browser, office and authorized financial acceptance |
| CE core with CRM/Accounting absent, then empty-core uninstall | Local lifecycle harness passed on the isolated final test databases; no tenant/form/attachment data existed and no HTTP request was allowed | New exact-head CI lane must pass after publication; this does not prove uninstall of a populated deployment is safe |
| CE with optional `mfierp_crm` | Not implemented or tested | Explicit consent/identity crosswalk, duplicate resolution, direct-RPC isolation and approved onboarding; Won never creates a Fineract client |
| CE with optional `mfierp_account` | Not implemented or tested | Verify installed account capability and source-mapped read-only comparison, dates/currency/company/office and independent accounting review |
| Licensed EE core and optional adapters | `EE_NOT_TESTED` | Licensed pinned dependencies and independent install/upgrade/uninstall, role, browser and integration results |
| Optional summarized GL bridge | Disabled; not implemented or approved | Signed ownership/mapping policy, independent accountant review and separately authorized synthetic UAT |

## Empty-core lifecycle lane

`scripts/verify_core_lifecycle.py` runs through Odoo's shell after installation and upgrade. It requires Odoo 20 superuser mode, an exact `mfierp_test[_suffix]` database name and two explicit test environment flags. It refuses version drift, queued module operations, dependent/optional/proprietary modules, missing catalog/models, any tenant/transient row and even orphaned MFIERP attachments. It never clears those records to make the test pass.

The harness invokes Odoo's standard `button_immediate_uninstall()` once. A new registry and cursor then verify that MFIERP models, tables, fields, XML IDs, menus, crons, views, actions and access records are gone, while unrelated installed module versions and standard base references remain. Requests and urllib HTTP entry points are blocked during the operation. An unknown uninstall failure is not retried automatically. These guards support an isolated empty test database, not production removal or audit-data deletion.

The CI lane follows the existing clean-install and upgrade steps:

```sh
docker compose run --rm -T \
  -e MFIERP_TEST_CORE_LIFECYCLE=UNINSTALL_SYNTHETIC_ONLY \
  -e MFIERP_TEST_CORE_LIFECYCLE_DB=mfierp_test \
  odoo odoo shell --database=mfierp_test --no-http \
  < scripts/verify_core_lifecycle.py
```

Ordinary Python guard tests need no Odoo, database or network. Actual uninstallation requires the isolated shell lane and its observed report; unit mocks alone cannot earn its pass label. Do not point this script at demo, acceptance or populated databases.

## Pinned public CE source findings

At [Odoo revision `c40402fab8c1509f3c68cd9cc5140f7790611d99`](https://github.com/odoo/odoo/tree/c40402fab8c1509f3c68cd9cc5140f7790611d99), the public [CRM manifest](https://github.com/odoo/odoo/blob/c40402fab8c1509f3c68cd9cc5140f7790611d99/addons/crm/__manifest__.py) and [account manifest](https://github.com/odoo/odoo/blob/c40402fab8c1509f3c68cd9cc5140f7790611d99/addons/account/__manifest__.py) both declare LGPL-3. The account module is presented as Invoicing; its presence does not establish every Enterprise Accounting feature. Neither app was installed in the core-absence lane.

The public source declares [`crm.lead`](https://github.com/odoo/odoo/blob/c40402fab8c1509f3c68cd9cc5140f7790611d99/addons/crm/models/crm_lead.py#L85), [`account.account`](https://github.com/odoo/odoo/blob/c40402fab8c1509f3c68cd9cc5140f7790611d99/addons/account/models/account_account.py#L26) and [`account.move`](https://github.com/odoo/odoo/blob/c40402fab8c1509f3c68cd9cc5140f7790611d99/addons/account/models/account_move.py#L81). Account company membership uses `company_ids`, while leads and moves declare `company_id`. A future adapter must validate membership and company ownership against this actual source; an older single-company account assumption is insufficient. This is source research, not an installed-app test or permission to post ERP journals.

Fineract continues to own microfinance transactions and ledger. Odoo's independent ERP accounting, optional read-only reconciliation and any separately approved consolidated bridge retain the boundaries in [ADR 002](ODOO_20_EDITION_CRM_ACCOUNTING_ADR.md).
