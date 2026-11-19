# Mifos X parity evidence

The extended workspace contains **1,048 contracts**: 966 HTTP operations from the Oracle-hosted public Fineract OpenAPI definition, plus 79 separately source-reviewed command variants and three constrained default operations. **896 have typed forms; 152 remain blocked**. A form's availability is not proof of operator workflow parity, API correctness in every tenant configuration, or live acceptance.

The public API snapshot identifies Fineract 1.16.0-SNAPSHOT. Its canonicalized SHA-256 and component schemas are embedded in `addons/mfierp/services/catalog.json`. No host address, service credential or business observations are included. Apache metadata attribution and license accompany the catalog.

## Source comparison

The [machine-readable inventory](mifos-endpoints.json) compares 720 literal HTTP calls from 99 Mifos service/routing source files against the catalog. Source revision: `nandahtoon/Mifosx-web-app@34c7f278861ef25052f2e00d106d8527f5d270d3`. Each call has a source link and line number. Another 180 action components were collected; selected submit handlers were inspected to verify command names and payload transformations.

| Inventory status | Calls | Meaning |
| --- | ---: | --- |
| TYPED_CONTRACT_CANDIDATE | 650 | Compatible method/path and at least one typed candidate; command selection and complete workflow still require verification |
| CONTRACT_REQUIRES_SOURCE_WORK | 43 | Matching API metadata exists but no usable typed candidate |
| DYNAMIC_RESOURCE_REQUIRES_REVIEW | 25 | Resource itself is computed by the frontend; matching route templates alone are insufficient |
| NOT_IN_DEPLOYED_OPENAPI | 2 | No compatible published operation; investigate service ownership and deployment |

The inventory is intentionally conservative about verification: every `operator_workflow_verified` and `live_uat_verified` flag remains false. Matching ignores query strings and does not prove command or payload equivalence. Multiple frontend calls can share one backend operation, and one computed call can represent many workflows. These counts are not a percentage of product completion.

## Separately reviewed variants

`scripts/command_contracts.py` declares 79 fixed commands, reviewed against the pinned component `submit()` implementations. The compiled entries include their source links. They cover client activation/reactivation/closure/rejection/withdrawal/staff assignment/savings linkage/transfers; loan approval/rejection/withdrawal/disbursement to savings/officer assignment/reversals/closure/waiver/recovery/charge-off; savings lifecycle/officer changes; fixed and recurring deposit approval/rejection/withdrawal/closure; savings holds/blocking/as-of interest; group and center activation/closure; group staff assignment; shares activation/approval/rejection/closure/purchase/redemption/reversal; manager-only role enable/disable, survey activation/deactivation and job execution without custom parameters; loan reschedule submission/approval/rejection/pending reads; charge payment/waiver/inactivation; and provisioning journal generation/recreation.

Each variant exposes exactly one command value. The unresolved parent operation remains visible as a gap; no generic command textbox can bypass it. Loan-product fee/penalty accounting mappings are narrowed to source-confirmed charge/account IDs, avoiding recursive response projections. Java DateParam and MIME wrapper schemas are normalized to their actual wire types. Six v2 operations use the same configured host and tenant with a fixed version selector. Manual Fineract journal creation uses its typed default POST contract without a free-form command. A separate loan application contract permits declared borrower/product fields and explicitly excludes tenant-defined datatables; its unresolved generic parent remains blocked.

## Remaining work

- Review the 152 blocked contracts: multiplexed commands, opaque or tenant-defined data objects, unsupported body encodings, authentication/session integrations and non-API metadata endpoints.
- Complete dedicated workflows for tenant-defined datatables, surveys/questionnaires, collection sheets, complex group/JLG/GLIM/GSIM lending, re-age/refinance and full rescheduling acceptance, advanced deposit settlement, bulk processing, report authoring and external integrations. Some underlying typed operations are already accessible; complete screen behavior remains unverified.
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
