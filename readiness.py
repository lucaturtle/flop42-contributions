"""Offline receipt and release-integrity helpers. No network or signer exists here."""
import hashlib
import json
import math
import re
import stat
import csv
from pathlib import Path

DIGEST = re.compile(r"[0-9a-f]{64}\Z")
FIELDS = {"schema", "mode", "workload_id", "input_sha256", "result_sha256",
          "logical_agent", "common_operator", "real_token_spend", "quality", "external_reference"}


def strict_json(raw):
    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("nonfinite JSON")
        return number

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique, parse_float=finite_float,
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
    if (not isinstance(workload_id, str) or not isinstance(input_digest, str)
            or not re.fullmatch(r"W[0-9]{2}", workload_id) or not DIGEST.fullmatch(input_digest)):
        raise ValueError("invalid workload identity")
    return hashlib.sha256(canonical([workload_id, input_digest])).hexdigest()


def verify_package(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("package root must be a real directory")
    root = root.resolve()
    manifest_path = root / "manifest.json"
    if manifest_path.is_symlink() or not stat.S_ISREG(manifest_path.stat().st_mode):
        raise ValueError("manifest must be a regular file")
    manifest = strict_json(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or set(manifest) != {"schema", "files"} or manifest["schema"] != "flop42-package-v1":
        raise ValueError("invalid package manifest")
    files = manifest["files"]
    if not isinstance(files, dict) or not files:
        raise ValueError("empty manifest")
    actual = set()
    for candidate in root.rglob("*"):
        if candidate.is_symlink():
            raise ValueError("symlink in package")
        if not candidate.is_file() and not candidate.is_dir():
            raise ValueError("special file in package")
        if candidate.is_file() and candidate != manifest_path:
            actual.add(candidate.relative_to(root).as_posix())
    if actual != set(files):
        raise ValueError("missing or unlisted package files")
    for name, expected in files.items():
        relative = Path(name)
        if (relative.is_absolute() or ".." in relative.parts or "\\" in name
                or relative.as_posix() != name or name == "manifest.json"):
            raise ValueError("unsafe manifest path")
        if not isinstance(expected, str) or not DIGEST.fullmatch(expected):
            raise ValueError("invalid manifest digest")
        if hashlib.sha256((root / relative).read_bytes()).hexdigest() != expected:
            raise ValueError("package file digest mismatch")
    return len(files)


def verify_evidence(root):
    """Verify this release's internal links, not authorship or real execution."""
    root = Path(root)
    verified = verify_package(root)

    def read(name):
        return strict_json((root / name).read_text(encoding="utf-8"))

    manifest = read("manifest.json")["files"]
    plan = read("workloads.json")
    if (not isinstance(plan, dict)
            or set(plan) != {"schema", "mode", "common_operator_control", "workloads"}
            or plan["schema"] != "flop42-prepared-workloads-v1"
            or plan["mode"] != "offline-preparation"
            or plan["common_operator_control"] is not True):
        raise ValueError("invalid offline plan")
    jobs = plan["workloads"]
    if not isinstance(jobs, list) or len(jobs) != 12:
        raise ValueError("expected twelve prepared workloads")
    owners = {}
    identifiers = set()
    required = {"id", "objective", "input", "roles", "expected_output", "quality_gate",
                "status", "live_dispatch", "provider", "model", "real_token_budget",
                "network_retries", "external_receipt"}
    for job in jobs:
        if not isinstance(job, dict) or set(job) != required:
            raise ValueError("invalid workload fields")
        ident = job["id"]
        if not isinstance(ident, str) or not re.fullmatch(r"W(?:0[1-9]|1[0-2])", ident) or ident in identifiers:
            raise ValueError("invalid or duplicate workload")
        identifiers.add(ident)
        if (job["status"] != "prepared-not-executed" or job["live_dispatch"] is not False
                or any(job[k] is not None for k in ("provider", "model", "external_receipt"))
                or any(type(job[k]) is not int or job[k] != 0
                       for k in ("real_token_budget", "network_retries"))):
            raise ValueError("workload execution gate must stay closed")
        for field in ("objective", "expected_output", "quality_gate"):
            if not isinstance(job[field], str) or not job[field].strip():
                raise ValueError("missing workload description")
        pin = job["input"]
        if (not isinstance(pin, dict) or set(pin) != {"path", "sha256"}
                or not isinstance(pin["path"], str) or pin["path"] not in manifest
                or pin["sha256"] != manifest[pin["path"]]):
            raise ValueError("workload input pin mismatch")
        if not isinstance(job["roles"], list) or not job["roles"]:
            raise ValueError("missing logical roles")
        for agent in job["roles"]:
            if type(agent) is not int or not 0 <= agent <= 41 or agent in owners:
                raise ValueError("invalid or duplicate role assignment")
            owners[agent] = ident
    if set(owners) != set(range(42)):
        raise ValueError("incomplete role coverage")
    with (root / "agent-assignments.csv").open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["agent", "existing_alias", "role", "workload",
                                 "distinct_deliverable", "status", "common_operator"]:
            raise ValueError("invalid assignment columns")
        rows = list(reader)
    if len(rows) != 42:
        raise ValueError("expected 42 assignment rows")
    seen = set()
    for row in rows:
        name = row["agent"]
        if not isinstance(name, str) or not re.fullmatch(r"Agent [0-9]{2}", name) or name in seen:
            raise ValueError("invalid or duplicate assignment row")
        seen.add(name)
        agent = int(name[-2:])
        if (agent not in owners or row["existing_alias"] != f"bot-{agent + 1:02d}"
                or row["workload"] != owners[agent] or row["common_operator"] != "true"
                or row["status"] != "assigned-not-executed"
                or not row["role"] or not row["distinct_deliverable"] or None in row):
            raise ValueError("assignment does not match workload plan")
    receipt = read("offline-diagnostic-receipt.json")
    expected_receipt = {
        "schema": "flop42-coordinator-diagnostic-v1", "mode": "offline",
        "executed_by": "coordinator", "common_operator": True,
        "real_token_spend": 0, "external_reference": None,
        "quality": "known-defects-reproduced", "finding_count": 5,
        "input_sha256": manifest["fixtures/workbench/src/flop_workbench/core.py"],
        "result_sha256": manifest["queue-observations.json"],
        "probe_sha256": manifest["probe_queue.py"],
    }
    if canonical(receipt) != canonical(expected_receipt):
        raise ValueError("diagnostic receipt mismatch; no agent-job execution is claimed")
    observations = read("queue-observations.json")
    if (not isinstance(observations, dict)
            or observations.get("mode") != "offline-counterexamples"
            or type(observations.get("live_requests")) is not int or observations["live_requests"] != 0
            or type(observations.get("real_token_spend")) is not int or observations["real_token_spend"] != 0):
        raise ValueError("invalid diagnostic mode")
    findings = observations.get("findings")
    if (not isinstance(findings, list) or len(findings) != 5
            or any(not isinstance(f, dict) or not isinstance(f.get("id"), str) for f in findings)
            or {f["id"] for f in findings} != {"Q1", "Q2", "Q3", "Q4", "Q5"}
            or any(f.get("defect_reproduced") is not True for f in findings)):
        raise ValueError("diagnostic findings incomplete")
    return {"verified_files": verified, "prepared_workloads": 12, "assigned_roles": 42,
            "coordinator_diagnostics": 5, "agent_jobs_executed_by_this_check": 0}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    args = parser.parse_args()
    print(json.dumps({**verify_evidence(args.package),
                      "claim": "local integrity only; not authenticity, acceptance or allocation"}))
