import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from readiness import validate_receipt, strict_json, verify_package, deduplicate_workload


def receipt():
    return dict(schema="flop42-offline-receipt-v1", mode="offline", workload_id="W01",
                input_sha256="a" * 64, result_sha256="b" * 64, logical_agent=0,
                common_operator=True, real_token_spend=0, quality="review-pending", external_reference=None)


class ReceiptTests(unittest.TestCase):
    def test_valid_receipt(self):
        self.assertEqual(len(validate_receipt(receipt())), 64)

    def test_live_claims_rejected(self):
        for key, value in [("mode", "testnet"), ("real_token_spend", 1), ("external_reference", "invented"),
                           ("common_operator", False), ("logical_agent", 42), ("logical_agent", True),
                           ("real_token_spend", False), ("quality", "accepted"), ("input_sha256", "A"*64)]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_receipt({**receipt(), key: value})

    def test_unknown_and_missing_fields(self):
        with self.assertRaises(ValueError): validate_receipt({**receipt(), "private_key": "forbidden"})
        invalid = receipt(); invalid.pop("common_operator")
        with self.assertRaises(ValueError): validate_receipt(invalid)

    def test_duplicate_json(self):
        with self.assertRaises(ValueError): strict_json('{"mode":"offline","mode":"testnet"}')

    def test_nonfinite_json(self):
        with self.assertRaises(ValueError): strict_json('{"value":NaN}')

    def test_deduplication_is_identity_independent(self):
        expected = deduplicate_workload("W01", "a"*64)
        self.assertEqual(expected, deduplicate_workload("W01", "a"*64))
        self.assertNotEqual(expected, deduplicate_workload("W02", "a"*64))


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "README.md").write_text("test fixture")
        (self.root / "manifest.json").write_text(json.dumps({"schema":"flop42-package-v1", "files":{
            "README.md": hashlib.sha256(b"test fixture").hexdigest()}}))

    def tearDown(self): self.tmp.cleanup()

    def test_valid_package(self): self.assertEqual(verify_package(self.root), 1)

    def test_changed_file(self):
        (self.root / "README.md").write_text("changed")
        with self.assertRaises(ValueError): verify_package(self.root)

    def test_extra_file(self):
        (self.root / "unexpected").write_text("unlisted")
        with self.assertRaises(ValueError): verify_package(self.root)

    def test_missing_file(self):
        (self.root / "README.md").unlink()
        with self.assertRaises(ValueError): verify_package(self.root)

    def test_symlink(self):
        (self.root / "link").symlink_to(self.root / "README.md")
        with self.assertRaises(ValueError): verify_package(self.root)

    def test_parent_escape(self):
        (self.root / "manifest.json").write_text(json.dumps({"schema":"flop42-package-v1", "files":{"../outside":"a"*64}}))
        with self.assertRaises(ValueError): verify_package(self.root)


if __name__ == "__main__": unittest.main()
