from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from flop_workbench import (
    EvidenceJournal,
    InferenceRequest,
    JobQueue,
    MockFlopProvider,
    WorkloadRunner,
    validate_activation_document,
)


class WorkbenchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_end_to_end_retains_result_spend_and_verifiable_evidence(self) -> None:
        queue = JobQueue(self.root / "queue.sqlite")
        journal = EvidenceJournal(self.root / "evidence.jsonl")
        provider = MockFlopProvider()
        self.assertTrue(provider.claim_faucet()["claimed"])
        request = InferenceRequest(
            workload="protocol-drift",
            prompt="Compare the current FLOP protocol draft with the last verified snapshot.",
            metadata={"source_class": "A-or-B"},
        )
        job_id = queue.enqueue(request)
        self.assertEqual(queue.enqueue(request), job_id)

        self.assertEqual(WorkloadRunner(queue, provider, journal).run_once(), job_id)
        record = queue.get(job_id)
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["request"]["prompt"], request.prompt)
        self.assertEqual(record["result"]["request_sha256"], request.fingerprint())
        self.assertEqual(len(provider.get_spend_history()), 1)
        self.assertTrue(journal.verify())
        queue.close()

    def test_expired_lease_is_resumable_and_owner_guarded(self) -> None:
        now = [100.0]
        queue = JobQueue(self.root / "queue.sqlite", clock=lambda: now[0])
        job_id = queue.enqueue(InferenceRequest("tests", "Generate regression tests."))
        first = queue.lease_next("worker-a", lease_seconds=5)
        self.assertIsNotNone(first)
        self.assertIsNone(queue.lease_next("worker-b"))
        now[0] = 106.0
        resumed = queue.lease_next("worker-b")
        self.assertEqual(resumed.id, job_id)
        with self.assertRaises(RuntimeError):
            queue.complete(job_id, "worker-a", {"status": "completed"})
        queue.close()

    def test_retry_becomes_terminal_at_bound(self) -> None:
        now = [100.0]
        queue = JobQueue(self.root / "queue.sqlite", clock=lambda: now[0])
        job_id = queue.enqueue(
            InferenceRequest("debug", "Diagnose a failing trace."), max_attempts=2
        )
        first = queue.lease_next("worker")
        queue.fail(first, "worker", "transient", retry_delay=2)
        self.assertEqual(queue.get(job_id)["status"], "queued")
        self.assertIsNone(queue.lease_next("worker"))
        now[0] = 102.0
        second = queue.lease_next("worker")
        queue.fail(second, "worker", "permanent")
        self.assertEqual(queue.get(job_id)["status"], "failed")
        queue.close()

    def test_evidence_tampering_is_detected(self) -> None:
        path = self.root / "evidence.jsonl"
        journal = EvidenceJournal(path)
        journal.append({"kind": "one"})
        journal.append({"kind": "two"})
        records = path.read_text(encoding="utf-8").splitlines()
        changed = json.loads(records[0])
        changed["event"]["kind"] = "tampered"
        path.write_text(
            "\n".join([json.dumps(changed), records[1]]) + "\n", encoding="utf-8"
        )
        self.assertFalse(journal.verify())

    def test_activation_gate_accepts_only_explicit_official_evidence(self) -> None:
        valid = {
            "mode": "testnet",
            "source_url": "https://flop.finance/teaser/",
            "source_sha256": "a" * 64,
            "confirmed_by_operator": True,
        }
        validate_activation_document(valid)
        with self.assertRaises(ValueError):
            validate_activation_document(
                {**valid, "source_url": "https://flop-faucet.example/"}
            )
        with self.assertRaises(ValueError):
            validate_activation_document({**valid, "confirmed_by_operator": False})


if __name__ == "__main__":
    unittest.main()
