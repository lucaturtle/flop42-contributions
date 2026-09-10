# V2 coordinator review

## V3 licensing addendum

The operator reported v2 "reviewed and approved" and subsequently authorized
Apache-2.0 for original material. This is recorded as operator-reported approval,
not a newly verified independent audit. V3 supplies the root LICENSE, source
license headers, scope notes, and the previously omitted upstream TCLK NOTICE.
The exact patch and frozen workbench are unchanged. Runtime behavior is unchanged;
metadata hashes and test evidence are refreshed for v3.

The historical license-decision gate below is now resolved. The external upstream
recheck, no-live-execution safeguards, and distinction between reported and
independently verified approval remain. This package was not uploaded by the agent.

## Historical v2 report (retained)

Scope: the local v1 contribution export and a separate v2 revision. The GitHub
upload was not accessed or changed. This is another coordinator review, not an
independent security audit. Neither version is declared production-ready.

## Findings and fixes

| Finding | Evidence in v1 | V2 action |
|---|---|---|
| Nonfinite JSON overflow | `strict_json("1e999")` returns infinity although NaN/Infinity tokens are rejected | Reject overflowing floats; test finite values and nested duplicate members |
| Hash-only validation misses contradictory evidence | Rehashing an edited plan bypasses the old file-only checker | Check workload input pins, closed execution gates, exact role coverage and CSV consistency |
| Incorrect diagnostic attribution | Receipt names logical Agent 00 and W02, although W02 is assigned to roles 06/28/29; aggregate probe was coordinator-executed | Use a dedicated coordinator diagnostic receipt with probe/input/result hashes; no job execution credit |
| Diagnostics could overstate reproduction | Q1/Q2 had literal true flags; Q4 accepted any caught RuntimeError | Derive flags from observed states and test exact counterexamples |
| Special files omitted from inventory | Nonregular entries were not rejected | Reject special files, symlink roots/manifests/directories, and noncanonical manifest paths |
| Publication language could become stale | Upstream status written in present tense; local review could be mistaken for independent approval | Date the retained source snapshot and state remaining review gates |

## Verification and privacy

The current run results are recorded in `verification-summary.json` and
`package-tests.txt`. The build regenerates linked input hashes, diagnostic evidence,
and the manifest, then tests a clean extracted archive. The TCLK patch and original
fixture remain byte-for-byte unchanged; the 178 TCLK tests are historical v1 evidence,
not newly executed in this v2 review.

The export uses the original fixed file list plus the two new regression test files,
this review and license notes. Automated screening checks for private path/key/token
markers and disallowed file types. This is risk reduction, not proof that arbitrary
secret formats cannot exist. No private bot state is opened or copied.

## Remaining gates

1. Keep the upload private until an independent reviewer approves this exact v2
   material revision. Do not carry v1 or TCLK-only approval over to new material.
2. Select a license for the new original material; retain upstream notices.
3. Recheck current upstream code and overlapping PRs before submitting the TCLK patch.
4. The five queue limitations remain intentionally preserved in a frozen fixture.
   A repaired production queue needs a separate implementation and adversarial review.
5. No live provider, spend, faucet, Technocore sends, public posting or creator
   application submission is enabled by this package.

Prepared roles remain assignments, not execution claims. W37 is operator-supplied
history, not fresh read-back. File integrity and internal consistency establish
neither publisher authenticity, external acceptance nor airdrop entitlement.
