"""Offline receipt and release-integrity helpers. No network or signer exists here."""
import hashlib
import json
import re
from pathlib import Path

DIGEST = re.compile(r"[0-9a-f]{64}\Z")
FIELDS = {"schema", "mode", "workload_id", "input_sha256", "result_sha256",
          "logical_agent", "common_operator", "real_token_spend", "quality", "external_reference"}


def strict_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def validate_receipt(receipt):
    if not isinstance(receipt, dict) or set(receipt) != FIELDS:
        raise ValueError("receipt has missing or extra fields")
    if receipt["schema"] != "flop42-offline-receipt-v1" or receipt["mode"] != "offline":
        raise ValueError("only explicitly offline evidence is accepted")
    if type(receipt["logical_agent"]) is not int or not 0 <= receipt["logical_agent"] <= 41:
        raise ValueError("logical agent must be 00 through 41")
    if receipt["common_operator"] is not True:
        raise ValueError("common control disclosure must be retained")
    if type(receipt["real_token_spend"]) is not int or receipt["real_token_spend"] != 0:
        raise ValueError("offline results cannot claim real spend")
    if receipt["quality"] not in ("pass", "fail", "review-pending"):
        raise ValueError("invalid quality verdict")
    if receipt["external_reference"] is not None:
        raise ValueError("offline evidence cannot claim an external receipt")
    if not isinstance(receipt["workload_id"], str) or not re.fullmatch(r"W[0-9]{2}", receipt["workload_id"]):
        raise ValueError("invalid workload identifier")
    for field in ("input_sha256", "result_sha256"):
        if not isinstance(receipt[field], str) or not DIGEST.fullmatch(receipt[field]):
            raise ValueError("invalid digest")
    return hashlib.sha256(canonical(receipt)).hexdigest()


def deduplicate_workload(workload_id, input_digest):
    # Agent count/aliases are intentionally absent: same work is not 42 contributions.
    if not re.fullmatch(r"W[0-9]{2}", workload_id) or not DIGEST.fullmatch(input_digest):
        raise ValueError("invalid workload identity")
    return hashlib.sha256(canonical([workload_id, input_digest])).hexdigest()


def verify_package(root):
    root = Path(root).resolve()
    manifest_path = root / "manifest.json"
    if manifest_path.is_symlink():
        raise ValueError("symlink manifest")
    manifest = strict_json(manifest_path.read_text())
    if not isinstance(manifest, dict) or set(manifest) != {"schema", "files"} or manifest["schema"] != "flop42-package-v1":
        raise ValueError("invalid package manifest")
    files = manifest["files"]
    if not isinstance(files, dict) or not files:
        raise ValueError("empty manifest")
    actual = set()
    for candidate in root.rglob("*"):
        if candidate.is_symlink():
            raise ValueError("symlink in package")
        if candidate.is_file() and candidate != manifest_path:
            actual.add(candidate.relative_to(root).as_posix())
    if actual != set(files):
        raise ValueError("missing or unlisted package files")
    for name, expected in files.items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe manifest path")
        if not isinstance(expected, str) or not DIGEST.fullmatch(expected):
            raise ValueError("invalid manifest digest")
        if hashlib.sha256((root / relative).read_bytes()).hexdigest() != expected:
            raise ValueError("package file digest mismatch")
    return len(files)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    args = parser.parse_args()
    print(json.dumps({"verified_files": verify_package(args.package),
                      "claim": "local integrity only; not authenticity, acceptance or allocation"}))
