# FLOP-42 contribution and inference-readiness package

An independent, common-operator engineering contribution. Not a FLOP Labs product,
an eligibility checker, a faucet, or an allocation claim.

## What is actually delivered

1. The existing TCLK duplicate-object-key patch, unchanged from its September 4
   independently reviewed revision; 178 tests rechecked September 10.
2. Five reproducible counterexamples against our own original offline workbench.
   These are not defects attributed to FLOP's chain or Technocore.
3. A small offline receipt/package-integrity verifier with 12 passing unit tests.
4. Twelve useful, input-pinned workload specifications and 42 distinct logical-role
   assignments. Assignments are a plan, not evidence of 42 independent executions.
5. A creator-interest application draft and a public contribution post draft.

## Safety and status

- Live provider, token spending, faucet claiming, signing, posting and referral actions: absent.
- Real FLOP spent: zero. All mock balances are fictional test integers.
- The original workbench is included only as a frozen test fixture with known defects.
  Do not deploy it for paid inference or treat it as crash-safe.
- The new verifier and reports are self-tested and await independent review.
- The TCLK patch has prior independent review; publication still requires a chosen
  account/repository and a final upstream check. It is not submitted or accepted.
- Logical Agent 00–41 maps to the operator's existing bot-01–42 aliases. These are
  not 42 independent people/operators or guaranteed allocation units. Keys are excluded.
- W37 completion is preserved separately as operator-supplied historical evidence,
  not as freshly read-back results or an airdrop qualification certificate.

## Reproduce locally

Python 3.11+; standard library only. From this extracted package directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 readiness.py .
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -p 'test_readiness.py' -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=fixtures/workbench/src python3 probe_queue.py
```

The last command reports known defects. A successful reproduction is not a passing
production safety test. The checks use temporary local databases and no network.
The manifest verifies file integrity, not publisher identity or external acceptance.

For the TCLK patch, use a clean checkout of the base in `TCLK-SUBMISSION.md`, apply
`tclk-duplicate-key.patch`, and follow upstream AGENTS.md. The existing working tree
was preserved; do not reset it or apply the same patch to it again.

## Before real testnet inference

Require current official endpoint/account/provider specifications, explicit operator
authorization, caps, price units, request idempotency and read-back reconciliation.
Resolve the local queue findings before adding any live adapter. Store actual session,
settlement and usage evidence separately from mock/local receipts. No token purchase
or wallet replacement is required for this package.

`workloads.json` describes expected outputs and review gates; it does not silently
queue network work. Its budget is zero and every external execution gate is closed.

## Attribution and publication

Publish one coherent repository/release, not 42 near-identical submissions. Attribute
completed work to its evidence; label the role table as proposed work allocation.
Retain upstream TCLK attribution in `TCLK-LICENSE`. No private keys, identity manifest,
local state database, environment file or personal contact details are in this package.

Separate lifecycle states: prepared → independently reviewed → submitted → accepted
→ merged → externally used. Each requires its own evidence; none implies a reward.
