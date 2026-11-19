# Functional coverage

The original focused workspace provides 21 reviewed write operations. Versions 20.0.2.0.0 through 20.0.5.0.0 add the extended typed workspace described below. It does **not** establish full Mifos X feature parity. The table documents the focused screens; “remain upstream” means those dedicated screen workflows have not yet been verified, even where an underlying API form is now available.

## Extended workspace

Open **Extended Workflows**, choose an available contract and connection, load fields, then open Details to edit nested sections or add typed collection rows. Reads return an escaped table/structured preview or a bounded authenticated file download. Writes create an immutable command for a different checker; administrator operations require an independent administrator. “More Workflows” on a portfolio record carries its connection and target into compatible forms.

The pinned catalog contains 966 API operations plus 100 fixed source-reviewed command variants and 13 reviewed forms without a command parameter, yielding 927 typed forms and 152 visible blocked contracts. Forms span documents, identifiers, addresses, household, collateral, charges, transfers, deposits, shares, products, organization, accounting, reports and administration. This is contract-level access, not a claim that each Mifos screen or tenant-specific business flow has passed acceptance. See the [parity evidence and remaining work](parity/README.md).

Files are copied into protected command storage with SHA-256 review evidence; bytes never appear in JSON audit payloads. Finalized file content is purged after seven days; pending and uncertain content is retained. Deployment secret references are bound by HMAC to the reviewed value; changed secrets cause dispatch validation to fail. Product/configuration and ledger administration forms require the manager role. Revoked or archived participants and inactive connections cannot dispatch previously approved work.

| Mifos X area | Native Odoo behavior | Boundary |
| --- | --- | --- |
| Organization | Offices/staff directory; tenant/company connections | Office/staff CRUD and hierarchy configuration remain upstream |
| Clients | Search/filter/detail; create inactive client; activate | KYC/document upload, identifiers, household, addresses and client transfers remain upstream |
| Groups and centers | Search/detail; create inactive entity; activate | Native membership and repeating meeting workflows are available through More Workflows; attendance and collection sheet completion remain outstanding |
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

## Rescheduling and provisioning navigation

Operations → Loan Rescheduling offers source-reviewed submission, list/pending views, approval and rejection forms. From a loan, More Workflows includes linked reschedule forms with the parent loan ID populated only in the declared body/query field. Reviewers enter the remote reschedule request ID for approval/rejection. Accounting and Reports → Provisioning Workflows exposes reference reads and administrator-reviewed journal generation/recreation. These local native paths are tested; tenant-specific financial acceptance is outstanding.

Portfolio → Deposit Workflows provides native fixed/recurring deposit cash, adjustment/reversal and lifecycle forms, plus closure and transaction template reads. It is a workflow catalog, not a synchronized account snapshot list. Fineract determines maturity, balances and closure eligibility. Unknown outcomes require reconciliation. Open workflow forms are invalidated when their pinned API contract changes.

Group/center records now link to scoped meeting creation, recurrence editing, meeting-date rescheduling and calendar reads. Portfolio → Group and Center Workflows also exposes membership association/disassociation, client transfers and default reference templates. Membership arrays are bounded, non-empty and unique; transfer rows contain explicit client IDs. Fineract enforces active-loan, membership and schedule rules. Specialized repeating meeting forms do not cover every one-off calendar or attendance workflow.
