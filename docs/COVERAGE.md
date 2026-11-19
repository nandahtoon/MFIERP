# Functional coverage

This release provides a native Odoo operational integration with 21 reviewed write operations. It does **not** reproduce every screen in the much larger Mifos X application. The boundaries below are part of the release contract.

| Mifos X area | Native Odoo behavior | Boundary |
| --- | --- | --- |
| Organization | Offices/staff directory; tenant/company connections | Office/staff CRUD and hierarchy configuration remain upstream |
| Clients | Search/filter/detail; create inactive client; activate | KYC/document upload, identifiers, household, addresses and client transfers remain upstream |
| Groups and centers | Search/detail; create inactive entity; activate | Membership management, meetings, attendance and collection sheets remain upstream |
| Loan products | Search/detail and administrator JSON; product-derived application defaults | Product configuration and advanced strategy setup remain upstream |
| Loans | Individual application, approval, disbursement, rejection, applicant withdrawal, repayment, write-off and closure | Group/JLG/GLIM, co-borrowers, rescheduling, refinance, tranche management, refunds and reversals remain upstream |
| Loan detail | Principal/outstanding, repayment schedule, transactions and charges from remote responses | Refresh explicitly; Fineract owns calculations and validation |
| Savings products | Search/detail and administrator JSON | Product configuration remains upstream |
| Savings | Application, approval, activation, rejection, deposit, withdrawal and closure | Interest posting, holds, overdraft setup, tax changes, GSIM and transaction reversal remain upstream |
| Savings detail | Balance, transactions and charges | Refresh explicitly; no local interest computation |
| Charge definitions | Search/detail | Adding, collecting and waiving account charges remain upstream |
| Accounting | GL account and journal catalogs with purpose-specific remote projections for administrators | No automatic Odoo account.move posting, double-booking or local ledger synchronization; manual journal/reversal/closing remains upstream |
| Reports | Report catalog; native table output with optional office/client/date/currency parameters | Maximum 5,000 output rows; report-specific parameters, Pentaho/export formats and SQL authoring remain upstream |
| Controls | Maker/checker, company isolation, immutable payload, durable reservation, idempotency key, audit references and reconciliation | No office-level user isolation, business duplicate detection or automatic remote maker-checker completion |
| Operations | Manual full sync; opt-in 15-minute sync; one-minute approved command dispatch | 50 pages per resource, 200 rows per page; bulk sync is atomic and requires all configured read permissions |
| Fixed/recurring deposits, shares, remittances, credit bureau, collateral, surveys, notifications, system administration | Not implemented | Use existing Mifos X workflows; add independently reviewed modules before claiming parity |

## Supported write operations

`create_client`, `create_group`, `create_center`, `activate_client`, `activate_group`, `activate_center`, `create_loan`, `approve_loan`, `disburse_loan`, `reject_loan`, `withdraw_loan`, `repay_loan`, `writeoff_loan`, `close_loan`, `create_savings`, `approve_savings`, `activate_savings`, `reject_savings`, `deposit_savings`, `withdraw_savings`, `close_savings`.

All create operations submit inactive entities or pending applications; activation/approval is a separate, independently reviewed remote request. Availability and required fields depend on the tenant's product and configuration. The initial forms cover standard individual loans and savings products. A tenant requiring extra application fields needs a reviewed schema/form extension, rather than an arbitrary JSON override.

## Acceptance sequence

1. Configure two companies and separate Fineract test tenants; verify isolation under each role.
2. Synchronize reference records. Confirm office/product IDs and currencies.
3. Submit a client, approve as a distinct checker, dispatch, refresh and activate it.
4. Apply for an individual loan using the tenant product's strategy/rates; approve and disburse; repay and compare remote schedule/balance.
5. Apply for savings; approve, activate, deposit, withdraw and compare remote balance.
6. Exercise remote 4xx, network timeout and a worker crash after reservation; confirm no automatic resend.
7. Reconcile independently with the Fineract audit and transaction IDs.
8. Run the relevant table reports and compare directly with Fineract.

Production acceptance requires this sequence against the intended Fineract version and products. Mock-based tests do not replace it.
