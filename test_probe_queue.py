# Copyright 2026 lucaturtle
# SPDX-License-Identifier: Apache-2.0
import unittest
from probe_queue import observe


class ProbeTests(unittest.TestCase):
    def test_exact_frozen_counterexamples(self):
        report = observe()
        findings = {f["id"]: f for f in report["findings"]}
        self.assertEqual(set(findings), {"Q1", "Q2", "Q3", "Q4", "Q5"})
        self.assertEqual(findings["Q1"]["observed"], "completed")
        self.assertEqual(findings["Q2"]["attempts"], [1, 2])
        self.assertEqual(findings["Q2"]["observed"], "stale-first-lease")
        self.assertEqual(findings["Q3"]["observed"], [1, 2, 3, 4])
        self.assertEqual(findings["Q4"]["observed"], {
            "job_status": "completed", "journal_entries": 0,
            "journal_append_attempts": 1, "raised": "job lease is not held by this worker"})
        self.assertEqual(findings["Q5"]["observed"], {"same_session": True, "mock_charges": 2})
        self.assertTrue(all(f["defect_reproduced"] is True for f in findings.values()))
        self.assertEqual(report["live_requests"], 0)
        self.assertEqual(report["real_token_spend"], 0)

    def test_repeated_probe_is_deterministic(self):
        self.assertEqual(observe(), observe())
