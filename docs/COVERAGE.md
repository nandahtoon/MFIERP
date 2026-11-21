# Functional coverage

The original focused workspace provides 21 reviewed write operations. Versions 20.0.2.0.0 through 20.0.9.0.0 add the extended typed workspace described below; 20.0.10.0.0 tightens outcome verification and historical status presentation. It does **not** establish full Mifos X feature parity. The table documents the focused screens; “remain upstream” means those dedicated screen workflows have not yet been verified, even where an underlying API form is now available.

## Extended workspace

Open **Extended Workflows**, choose an available contract and connection, load fields, then open Details to edit nested sections or add typed collection rows. Reads return an escaped table/structured preview or a bounded authenticated file download. Writes create an immutable command for a different checker; administrator operations require an independent administrator. “More Workflows” on a portfolio record carries its connection and target into compatible forms.

The pinned catalog contains 966 API operations plus 108 fixed source-reviewed command variants and 23 reviewed forms without a command parameter, yielding 945 typed forms and 152 visible blocked contracts. Forms span documents, identifiers, addresses, household, collateral, charges, transfers, deposits, shares, products, organization, accounting, reports and administration. This is contract-level access, not a claim that each Mifos screen or tenant-specific business flow has passed acceptance. See the [parity evidence and remaining work](parity/README.md).

Files are copied into protected command storage with SHA-256 review evidence; bytes never appear in JSON audit payloads. Finalized file content is purged after seven days; pending and uncertain content is retained. Deployment secret references are bound by HMAC to the reviewed value; changed secrets cause dispatch validation to fail. Product/configuration and ledger administration forms require the manager role. Revoked or archived participants and inactive connections cannot dispatch previously approved work.

| Mifos X area | Native Odoo behavior | Boundary |
| --- | --- | --- |
| Organization | Offices/staff directory; tenant/company connections | Office/staff CRUD and hierarchy configuration remain upstream |
| Clients | Search/filter/detail; create inactive client; activate | KYC/document upload, identifiers, household, addresses and client transfers remain upstream |
| Groups and centers | Search/detail; create inactive entity; activate | Native membership and repeating meeting workflows are available through More Workflows; scoped attendance and individual collection workflows are available; joint-liability collection-sheet completion remains outstanding |
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

All successful mutating dispatches remain **Remote Verification Pending**, including creation or financial responses with a resource ID. Response receipt has its own timestamp and does not fill current completion. Applied reconciliation is currently blocked for financial/resource workflows because no reviewed account/transaction/ledger verifier is implemented; a note, positive ID or RPC context cannot bypass that limit. Only the exact scheduler start/stop contracts support independently verified applied completion. A different administrator must handle either reconciliation outcome; confirmed-not-applied is manual investigation evidence and never triggers a resend. The collection preview remains a separately declared read, with no payment posting. See [outcome verification and upgrade impact](OUTCOME_VERIFICATION.md).

## Acceptance sequence

1. Configure two companies and separate Fineract test tenants; verify isolation under each role.
2. Synchronize reference records. Confirm office/product IDs and currencies.
3. After the required workflow verifiers exist and the synthetic lane is authorized, submit a client, approve as a distinct checker, dispatch, independently verify remote identity/status and then separately review activation.
4. Apply for an individual loan using the tenant product's strategy/rates; separately review each lifecycle command and verify its authoritative remote account, transaction, schedule and ledger effects before proceeding.
5. Apply for savings; independently verify each approval, activation, deposit and withdrawal against the remote account, transactions and ledger.
6. Exercise remote 4xx, network timeout and a worker crash after reservation; confirm no automatic resend.
7. Reconcile independently with the Fineract audit and transaction IDs.
8. Run the relevant table reports and compare directly with Fineract.

This is a future acceptance obligation, not an executable claim that the current release can complete these journeys. General financial applied-completion verifiers are not implemented. Production acceptance requires the full sequence against the intended Fineract version and products; mock-based tests do not replace it.

## Rescheduling and provisioning navigation

Operations → Loan Rescheduling offers source-reviewed submission, list/pending views, approval and rejection forms. From a loan, More Workflows includes linked reschedule forms with the parent loan ID populated only in the declared body/query field. Reviewers enter the remote reschedule request ID for approval/rejection. Accounting and Reports → Provisioning Workflows exposes reference reads and administrator-reviewed journal generation/recreation. These local native paths are tested; tenant-specific financial acceptance is outstanding.

Portfolio → Deposit Workflows provides native fixed/recurring deposit cash, adjustment/reversal and lifecycle forms, plus closure and transaction template reads. It is a workflow catalog, not a synchronized account snapshot list. Fineract determines maturity, balances and closure eligibility. Unknown outcomes require reconciliation. Open workflow forms are invalidated when their pinned API contract changes.

Group/center records now link to scoped meeting creation, recurrence editing, meeting-date rescheduling and calendar reads. Portfolio → Group and Center Workflows also exposes membership association/disassociation, client transfers and default reference templates. Membership arrays are bounded, non-empty and unique; transfer rows contain explicit client IDs. Fineract enforces active-loan, membership and schedule rules. Specialized repeating meeting forms do not cover every one-off calendar or attendance workflow.

Operations → Individual Collection Sheets provides separately approved preview generation and posting. Previews copy remote due/charge amounts without totaling them. Posting requires explicit amounts, one row per account, matching dates and a non-empty collection. Every posting remains Remote Verification Pending until accounts and transactions are reconciled. The initial scope supports loan repayments and savings/recurring deposit dues (types 100/300), not bulk disbursement or joint-liability collection posting. Group/center records also link to attendance templates, attendance lists and attendance submission with typed option objects.

Portfolio → Registered Data Tables exposes connection-scoped registrations refreshed by an administrator. Supported metadata produces typed string/text, integer, decimal, boolean, date and dropdown entry forms. Reads show at most 200 rows; creation, updates and deletion enter independent maker/checker review. Office/product entry writes require two different administrators. Data Tables on compatible portfolio records filters registrations to the connection and application type and prefills only the parent ID. Multi-row updates and deletion require one explicit entry ID. Metadata is pinned when fields are loaded and checked against Fineract again before reads or dispatch. Unsupported layouts, credential-bearing columns, datetime/JSON/binary fields and removed registrations are blocked. Table/schema administration, arbitrary queries, clearing values to NULL and inline application datatables remain outside this adapter; live tenant acceptance is outstanding.

Operations → Standing Instructions includes a separately reviewed update form for status, priority, dates, amount and recurrence. It cannot change transfer accounts or choose another command. Accounting and Reports → Provisioning Workflows includes creation and editing with explicit product IDs, category definitions and liability/expense account IDs. Category rows and products are non-empty and unique; maximum age must exceed minimum age. Both maker and checker must be administrators. Fineract determines provisions and validates the tenant's category/account configuration; Odoo creates no ledger entries.

Products → Share Dividends includes reads, plan creation and separate approval. Fineract calculates allocations. Plan creation retains the returned dividend subresource ID; creation and approval always await remote reconciliation, and approval does not establish completed payment. Configuration → Scheduler Workflows includes fixed start/stop commands, status and existing job contracts, restricted to administrators in Python. Commands without an identifying response stay pending remote verification. No new arbitrary job parameters or automatic bulk execution are exposed.

Operations → Loan Officer Reassignment accepts 1–100 explicit unique loan IDs, distinct source/destination officers and an assignment date. It excludes the frontend-only office selector from the transmitted body. Configuration → Holiday Workflows includes separately reviewed activation without a body. Both workflows require two administrators and remote verification of every affected assignment/schedule. A savings account's More Workflows includes the fixed updateWithHoldTax PUT command with a required boolean, including false; Fineract owns tax eligibility, calculation and posting.

Scheduler start/stop can be reconciled by an administrator different from the maker, without inventing a resource ID, only after a fresh authenticated runtime-pinned GET confirms the exact expected boolean status and independent evidence is recorded. This exception is declared only for those two resource-less contracts. Negative IDs are rejected. Financial/resource applied completion remains blocked until reviewed authoritative verifiers exist; positive IDs alone do not meet that requirement.

Remote audit and checker-queue reads expose bounded administrator-only metadata. Submitted command JSON and unknown/nested payloads are excluded before persistence; raw downloads are disabled for these specialized reads. Remote approval/rejection remains blocked until a verified, separate remote checker identity is implemented.
