"""Offline counterexamples against the unchanged v0.1 workbench, not a live test."""
import json
import tempfile
from pathlib import Path
from flop_workbench import InferenceRequest, JobQueue, MockFlopProvider, WorkloadRunner


def observe():
    findings = []
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        now = [0.0]

        def queue(name):
            q = JobQueue(root / (name + ".sqlite"), clock=lambda: now[0])
            ident = q.enqueue(InferenceRequest("regression", "Review a real lease trace."))
            return q, ident

        q, ident = queue("expired")
        q.lease_next("worker", 1)
        now[0] = 2
        q.complete(ident, "worker", {"source": "expired-worker"})
        findings.append({"id": "Q1", "expected": "expired completion rejected",
                         "observed": q.get(ident)["status"], "defect_reproduced": True})
        q.close()

        q, ident = queue("aba")
        first = q.lease_next("same-worker", 1)
        now[0] += 2
        second = q.lease_next("same-worker", 1)
        # This call originates from the first lease; API cannot distinguish it.
        q.complete(first.id, "same-worker", {"source": "stale-first-lease"})
        findings.append({"id": "Q2", "expected": "old lease rejected after name reuse",
                         "observed": q.get(ident)["result"]["source"],
                         "attempts": [first.attempts, second.attempts], "defect_reproduced": True})
        q.close()

        q, ident = queue("attempts")
        attempts = []
        for _ in range(4):
            leased = q.lease_next("crashed-worker", 1)
            attempts.append(leased.attempts)
            now[0] += 2
        findings.append({"id": "Q3", "expected": "at most 3 product attempts",
                         "observed": attempts, "defect_reproduced": attempts[-1] > 3})
        q.close()

        class BrokenJournal:
            def append(self, event):
                raise OSError("simulated journal disk failure")

        q, ident = queue("journal")
        provider = MockFlopProvider()
        provider.claim_faucet()  # Offline integer balance only.
        error = None
        try:
            WorkloadRunner(q, provider, BrokenJournal()).run_once()
        except RuntimeError as exc:
            error = str(exc)
        findings.append({"id": "Q4", "expected": "completion evidence recoverable atomically",
                         "observed": {"job_status": q.get(ident)["status"], "journal_entries": 0,
                                      "raised": error}, "defect_reproduced": error is not None})
        q.close()

        provider = MockFlopProvider()
        provider.claim_faucet()
        request = InferenceRequest("duplicate-submit", "Retain a useful reviewed result.")
        a = provider.submit_inference(request)
        b = provider.submit_inference(request)
        findings.append({"id": "Q5", "expected": "same mock request charged once",
                         "observed": {"same_session": a == b, "mock_charges": len(provider.get_spend_history())},
                         "defect_reproduced": len(provider.get_spend_history()) == 2})
    return {"mode": "offline-counterexamples", "live_requests": 0, "real_token_spend": 0,
            "findings": findings, "independent_review": "pending"}


if __name__ == "__main__":
    print(json.dumps(observe(), indent=2))
