# Copyright 2026 lucaturtle
# SPDX-License-Identifier: Apache-2.0
"""Hostile metadata checks: rehash tampering so semantic validation is exercised."""
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from readiness import verify_evidence


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "package"
        shutil.copytree(Path(__file__).parent, self.root,
                        ignore=shutil.ignore_patterns("__pycache__", ".git"))

    def tearDown(self):
        self.tmp.cleanup()

    def rehash(self):
        files = {p.relative_to(self.root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in self.root.rglob("*") if p.is_file() and p.name != "manifest.json"}
        (self.root / "manifest.json").write_text(json.dumps({"schema": "flop42-package-v1", "files": files}))

    def change(self, name, modify):
        path = self.root / name
        value = json.loads(path.read_text())
        modify(value)
        path.write_text(json.dumps(value))
        self.rehash()

    def test_release_links(self):
        self.assertEqual(verify_evidence(self.root)["assigned_roles"], 42)

    def test_rehashed_stale_input(self):
        self.change("workloads.json", lambda p: p["workloads"][0]["input"].update(sha256="0"*64))
        with self.assertRaises(ValueError): verify_evidence(self.root)

    def test_rehashed_live_activation(self):
        self.change("workloads.json", lambda p: p["workloads"][0].update(live_dispatch=True))
        with self.assertRaises(ValueError): verify_evidence(self.root)

    def test_boolean_budget(self):
        self.change("workloads.json", lambda p: p["workloads"][0].update(real_token_budget=False))
        with self.assertRaises(ValueError): verify_evidence(self.root)

    def test_duplicate_roles(self):
        self.change("workloads.json", lambda p: p["workloads"][0]["roles"].append(0))
        with self.assertRaises(ValueError): verify_evidence(self.root)

    def test_boolean_role(self):
        self.change("workloads.json", lambda p: p["workloads"][0].update(roles=[True]))
        with self.assertRaises(ValueError): verify_evidence(self.root)

    def test_unknown_workload_field(self):
        self.change("workloads.json", lambda p: p["workloads"][0].update(approved=True))
        with self.assertRaises(ValueError): verify_evidence(self.root)

    def test_unsafe_input_path(self):
        self.change("workloads.json", lambda p: p["workloads"][0]["input"].update(path="../outside"))
        with self.assertRaises(ValueError): verify_evidence(self.root)

    def test_duplicate_workload(self):
        self.change("workloads.json", lambda p: p["workloads"][1].update(id="W01"))
        with self.assertRaises(ValueError): verify_evidence(self.root)

    def test_wrong_alias(self):
        path = self.root / "agent-assignments.csv"
        path.write_text(path.read_text().replace("bot-01", "bot-99"))
        self.rehash()
        with self.assertRaises(ValueError): verify_evidence(self.root)

    def test_receipt_false_attribution(self):
        self.change("offline-diagnostic-receipt.json", lambda p: p.update(logical_agent=0))
        with self.assertRaises(ValueError): verify_evidence(self.root)

    def test_wrong_receipt_result(self):
        self.change("offline-diagnostic-receipt.json", lambda p: p.update(result_sha256="0"*64))
        with self.assertRaises(ValueError): verify_evidence(self.root)

    def test_receipt_boolean_spend(self):
        self.change("offline-diagnostic-receipt.json", lambda p: p.update(real_token_spend=False))
        with self.assertRaises(ValueError): verify_evidence(self.root)

    def test_incomplete_diagnostics(self):
        self.change("queue-observations.json", lambda p: p["findings"].pop())
        # Update the linked digest too: failure must be semantic, not a stale hash.
        digest = hashlib.sha256((self.root / "queue-observations.json").read_bytes()).hexdigest()
        self.change("offline-diagnostic-receipt.json", lambda p: p.update(result_sha256=digest))
        with self.assertRaises(ValueError): verify_evidence(self.root)


if __name__ == "__main__":
    unittest.main()
