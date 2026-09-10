# Prepared pull-request text — not yet submitted

Title: fix(frames): reject duplicate JSON object members before decoding

## Problem and scope

Related to https://github.com/flop-labs/tclk/issues/26 (duplicate-key question only).
The decoder currently delegates to JSON.parse, which loses duplicate members before
validation. Implementations can therefore disagree on whether the same received
frame is malformed. This patch rejects repeated decoded member names, including
nested and escape-equivalent keys, before ordinary parsing and frame validation.

Four changed paths: src/frames.ts, tests/tclk.test.ts, SPEC.md and CHANGELOG.md.
No golden-vector, emitted canonical-byte, settlement-rail or custody change.
The spec clarification is part of the proposed change, not a claimed maintainer ruling.

Base: 5cc4ab93efbc8999a3a7e1471b639deca25998ea.
Patch SHA-256: 063931ab10a9688a3f90269d097bb21ba5217a0e0d91accce086eb2d645b43d6.
Prior independent local review: September 4; exact revised hash approved.

## Verification refreshed September 10

- Frozen dependency install, using the existing offline cache: passed.
- Recursive build including workspace root: passed.
- Library: 105 passed; MCP: 40 passed; Worker: 33 passed.
- git diff --check: passed; patch hash unchanged.

## Overlap check

In the September 10 preparation snapshot, official main was at the base above and
issue #26 was open. All 61 then-open PR
titles/bodies were screened. Relevant implementation diffs were checked for #124,
#16 and #66. No equivalent decoder-wide duplicate-member check was identified in
that screen; this is not an exhaustive proof about every line of every PR.

PR #124 adds canonical re-encoding comparison at the MCP posting boundary. That
would also reject duplicate-key lines on that outbound route, but does not harden
the library decoder or arbitrary incoming transcripts. It is partial adjacent
coverage, not a reason to claim this patch is entirely unrelated. PR #66 adds
ASCII guards; #16 changes nested unknown-field handling. PR #68 is adjacent spec
wording. Recheck all of these immediately before submitting/rebasing.

## Attribution and limits

One common-operator project assisted by AI, not 42 independent contributions.
Credit the original interoperability report in #26. Tests were local, not paid
FLOP inference; no tokens, airdrop entitlement or external acceptance are claimed.
Operator-selected hosting account: lucaturtle. The operator reports uploading v1
to a private repository. Its contents were not read back in this local v2 review.
No upstream PR submission is claimed. Refresh the overlap screen before submission.
