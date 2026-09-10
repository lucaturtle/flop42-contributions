# Reproducible limitations in our offline workbench v0.1

Scope: the locally authored prototype, not official FLOP/Technocore software.
Evidence: `queue-observations.json`; exact target bytes are pinned in `manifest.json`.
Reviewer status: independent review pending. Original implementation unchanged.
V2 reruns the counterexamples and checks their exact observed states. This is
coordinator regression review, not independent approval or a production queue fix.

| ID | Reproduction | Observed result | Required improvement before live use |
|---|---|---|---|
| Q1 | Complete a job after its lease expires, before another claimant arrives | Completion succeeds | Require unexpired lease at commit |
| Q2 | Expire a lease, reuse the same worker name, then complete from the old lease | Old result wins | Bind completion/failure to a unique lease generation |
| Q3 | Repeatedly expire a job configured for three attempts | Fourth lease is granted | Enforce max attempts in the claim transaction, including crash recovery |
| Q4 | Make journal append fail after a successful mock inference | Job is completed with no journal receipt; error is replaced by a lease error | Persist completion and a recoverable evidence outbox atomically; reconcile export separately |
| Q5 | Submit the same request twice to MockFlopProvider | Same session ID but two mock debits | Make the mock idempotent and require an explicit real-provider idempotency contract |

Each reproduction uses a temporary SQLite database, simulated time, and/or a mock
provider. Q4 is a simulated disk error, not a destructive host test. No real funds,
keys or network are involved. Q5 is specifically a limitation of the test double.

The original five tests still pass: their coverage did not establish these stronger
guarantees. The correct response is to preserve counterexamples and add regression
coverage, not to reclassify the results as successful paid-inference readiness.

These diagnostics do not claim completion of the separate OPS-001/OPS-002 admission
plans: in particular, the 100-seed four-connection matrix has not been executed here.

Additional review boundary: the fixture's `validate_activation_document` only
checks supplied fields and a URL/digest shape. It neither fetches the document nor
verifies that its digest or contents establish live availability. It is not an
authorization gate for a future live adapter. The new package executes no adapter.
