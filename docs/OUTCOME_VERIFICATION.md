# Command outcome verification

Version `20.0.10.0.0` separates receiving a Fineract response from verifying its outcome. Every mutating response remains **Remote Verification Pending**, including responses containing `resourceId`, `commandId` or a dividend subresource ID. `response_received_at` records the returned response; `completed_at` stays empty while verification is pending. A command ID may represent Fineract's own maker/checker queue.

The non-posting individual collection preview is a separately declared POST-based read. A valid bounded preview may finish as Verified; its message explicitly states that no payment was posted. This exception cannot be selected by RPC context or an editable command parameter.

## Reconciliation procedure and current limits

1. Keep the original request, payload digest, idempotency key and remote references. Investigate using the same company, connection and tenant. Do not submit another command merely because a response was lost or a queue item remains pending.
2. An administrator different from the maker investigates either outcome. The command row lock serializes this investigation with dispatch. A note must contain at least 20 characters of independent evidence; credentials or unnecessary customer information do not belong in it.
3. Applied completion requires an operation-specific authoritative readback verifier. **No financial/resource-operation verifier is implemented yet.** A positive ID, an evidence note, a generic portfolio refresh or a forged context flag cannot mark such an operation applied. The server rejects that transition and leaves the command pending or uncertain.
4. Only the exact source-reviewed scheduler start/stop contracts support applied reconciliation today. The adapter revalidates the contract, clean runtime pin and authenticated `GET scheduler`; its `active` value must be a boolean matching the requested state. No resource ID may be fabricated. This confirms the current scheduler end state, not causality of a particular POST.
5. Confirmed Not Applied remains an independent administrator's manual investigation decision. The adapter records the investigator, note and terminal timestamp; an entered investigation resource ID is stored separately and never overwrites the references received from Fineract. It does not automatically prove absence of a remote transaction, resend the command or authorize a replacement. A replacement requires a separate reviewed submission after the investigation establishes it is safe.

The dispatch worker selects only Approved commands. Pending verification, uncertain, dispatching and migrated historical commands are never selected for automatic replay. Revoked roles, company isolation, distinct maker/checker, immutable request validation and the durable dispatch barrier remain enforced.

## Historical upgrade behavior

The post-upgrade migration runs through Odoo's versioned migration API. It processes bounded batches and preserves these cases:

| Existing record | Current state after upgrade | Retained evidence |
| --- | --- | --- |
| Non-preview Done, including a previous manual confirmation | Remote Verification Pending; current completion cleared | Original state, completion time, status message and reclassification time in historical fields |
| Remote Pending with an old completion timestamp | Remote Verification Pending; current completion cleared | The same original outcome metadata in historical fields |
| Completed non-posting preview with a preview digest | Completed preview retained | Existing preview, digest and timestamp |
| Other approval, uncertain or pending work without a completion timestamp | Existing state retained | Existing audit data |

Payloads, hashes, idempotency keys, maker/checker identities, approval times, remote IDs and previous resolution notes/investigators are preserved. An old completion time is not converted into a guessed response time. Repeating the migration does not overwrite its historical evidence or enqueue work. Historical details appear under Audit References in the native command form, alongside the current state.

Back up the database and filestore and disable dispatch during a controlled upgrade. A larger pending queue after upgrade represents previously unverified outcomes; it is not new remote activity or a financial reversal. Keep missing verifiers visible and do not clear the queue by resubmitting requests.

## Remaining financial verifier work

Each supported financial transition needs a source-reviewed correlation contract for the account, transaction, relevant schedule/balance and ledger effects, including currency, business/effective date, remote maker/checker state and reversal relationships. Fineract calculates these values. Same-account or same-date journal entries alone do not establish that they belong to this command.

The published journal API uses a string `transactionId`, distinct from a command's numeric resource ID. The pinned [Fineract journal reader](https://github.com/apache/fineract/blob/6a28754c6839fa64f5faf1873f9fcb52bc330fd9/fineract-provider/src/main/java/org/apache/fineract/accounting/journalentry/service/JournalEntryReadPlatformServiceImpl.java#L209) derives a numeric transaction detail reference from that string. An invented loan/savings prefix or a matching account/date is insufficient proof. Correlation and product-specific ledger expectations require further source review, independent financial review and separately authorized synthetic UAT.

Mocked local regressions cover response IDs without completion, lost/malformed responses, unsupported applied reconciliation, self-reconciliation denial, scheduler fresh reads, preview separation and repeatable historical migration. These controls prevent false completion; they do not establish financial parity, Oracle UAT or licensed Enterprise acceptance.
