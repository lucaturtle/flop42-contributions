# Copyright 2026 lucaturtle
# SPDX-License-Identifier: Apache-2.0
"""Regression checks for this export's licensing and upstream preservation."""
import hashlib
import unittest
from pathlib import Path

ROOT = Path(__file__).parent


class LicensingTests(unittest.TestCase):
    def test_root_license_and_scope(self):
        license_text = (ROOT / "LICENSE").read_text()
        self.assertIn("Version 2.0, January 2004", license_text)
        self.assertIn("Copyright 2026 lucaturtle", license_text)
        self.assertIn("operator-authorized", (ROOT / "LICENSE-NOTES.md").read_text())

    def test_upstream_notice_preserved(self):
        expected = ("tclk\nCopyright 2026 FLOP Labs\n\n"
                    "This product includes software developed at FLOP Labs (https://flop.network).\n\n"
                    "Licensed under the Apache License, Version 2.0. See LICENSE.\n")
        self.assertEqual((ROOT / "TCLK-NOTICE").read_text(), expected)
        self.assertIn(expected, (ROOT / "NOTICE").read_text())
        self.assertIn("Copyright 2026 FLOP Labs", (ROOT / "TCLK-LICENSE").read_text())

    def test_reviewed_patch_unchanged(self):
        self.assertEqual(hashlib.sha256((ROOT / "tclk-duplicate-key.patch").read_bytes()).hexdigest(),
                         "063931ab10a9688a3f90269d097bb21ba5217a0e0d91accce086eb2d645b43d6")

    def test_original_source_headers(self):
        for path in ROOT.glob("*.py"):
            with self.subTest(name=path.name):
                self.assertIn("SPDX-License-Identifier: Apache-2.0", path.read_text()[:150])
