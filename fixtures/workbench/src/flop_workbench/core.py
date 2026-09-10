"""Provider-neutral FLOP inference workbench.

No unpublished network API is assumed here. The only concrete provider is an
offline mock; a live adapter must implement FlopProvider after official
testnet specifications exist.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


@dataclass(frozen=True)
class InferenceRequest:
    workload: str
    prompt: str
    model: str = "mock-useful-v1"
    metadata: dict[str, Any] | None = None

    def fingerprint(self) -> str:
        return hashlib.sha256(_canonical(asdict(self)).encode()).hexdigest()


class FlopProvider(Protocol):
    """Interface to fill from official FLOP specifications, not guesses."""

    def get_balance(self) -> int: ...

    def claim_faucet(self) -> dict[str, Any]: ...

    def list_models(self) -> list[dict[str, Any]]: ...

    def submit_inference(self, request: InferenceRequest) -> str: ...

    def get_session_status(self, session_id: str) -> dict[str, Any]: ...

    def get_spend_history(self) -> list[dict[str, Any]]: ...


class MockFlopProvider:
    """Deterministic offline provider for queue, retry, and accounting tests."""

    def __init__(self, faucet_amount: int = 100_000) -> None:
        self._balance = 0
        self._faucet_amount = faucet_amount
        self._claimed = False
        self._sessions: dict[str, dict[str, Any]] = {}
        self._spend: list[dict[str, Any]] = []

    def get_balance(self) -> int:
        return self._balance

    def claim_faucet(self) -> dict[str, Any]:
        if self._claimed:
            return {"claimed": False, "amount": 0, "reason": "already claimed (mock)"}
        self._claimed = True
        self._balance += self._faucet_amount
        return {"claimed": True, "amount": self._faucet_amount}

    def list_models(self) -> list[dict[str, Any]]:
        return [{"id": "mock-useful-v1", "mode": "offline", "cost_per_unit": 1}]

    def submit_inference(self, request: InferenceRequest) -> str:
        units = max(1, (len(request.prompt) + 3) // 4)
        if units > self._balance:
            raise RuntimeError("insufficient mock balance")
        request_hash = request.fingerprint()
        session_id = "mock-" + request_hash[:24]
        result = {
            "session_id": session_id,
            "status": "completed",
            "model": request.model,
            "output": "mock-result:"
            + hashlib.sha256(request.prompt.encode()).hexdigest(),
            "request_sha256": request_hash,
            "units": units,
            "cost_flop": units,
            "latency_ms": 0,
        }
        self._balance -= units
        self._sessions[session_id] = result
        self._spend.append(
            {
                "session_id": session_id,
                "cost_flop": units,
                "workload": request.workload,
                "request_sha256": request_hash,
            }
        )
        return session_id

    def get_session_status(self, session_id: str) -> dict[str, Any]:
        if session_id not in self._sessions:
            raise KeyError(session_id)
        return dict(self._sessions[session_id])

    def get_spend_history(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._spend]


@dataclass(frozen=True)
class LeasedJob:
    id: str
    request: InferenceRequest
    attempts: int
    max_attempts: int


class JobQueue:
    """SQLite queue with idempotent enqueueing, leases, retries, and retained results."""

    def __init__(
        self, path: str | Path, clock: Callable[[], float] = time.time
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        self._db = sqlite3.connect(self.path, isolation_level=None, timeout=10)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                request_json TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('queued','running','completed','failed')),
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL,
                available_at REAL NOT NULL,
                leased_by TEXT,
                lease_until REAL,
                result_json TEXT,
                last_error TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )

    def close(self) -> None:
        self._db.close()

    def enqueue(
        self,
        request: InferenceRequest,
        *,
        max_attempts: int = 3,
        job_id: str | None = None,
    ) -> str:
        if not request.prompt.strip():
            raise ValueError("a useful workload requires a non-empty prompt")
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        identifier = job_id or request.fingerprint()
        now = self._clock()
        self._db.execute(
            """
            INSERT OR IGNORE INTO jobs
            (id, request_json, status, attempts, max_attempts, available_at, created_at, updated_at)
            VALUES (?, ?, 'queued', 0, ?, ?, ?, ?)
            """,
            (identifier, _canonical(asdict(request)), max_attempts, now, now, now),
        )
        return identifier

    def lease_next(self, worker: str, lease_seconds: float = 60) -> LeasedJob | None:
        if not worker or lease_seconds <= 0:
            raise ValueError("worker and a positive lease are required")
        now = self._clock()
        self._db.execute("BEGIN IMMEDIATE")
        try:
            row = self._db.execute(
                """
                SELECT * FROM jobs
                WHERE (status = 'queued' AND available_at <= ?)
                   OR (status = 'running' AND lease_until <= ?)
                ORDER BY created_at, id
                LIMIT 1
                """,
                (now, now),
            ).fetchone()
            if row is None:
                self._db.execute("COMMIT")
                return None
            self._db.execute(
                """
                UPDATE jobs
                SET status='running', attempts=attempts+1, leased_by=?, lease_until=?, updated_at=?
                WHERE id=?
                """,
                (worker, now + lease_seconds, now, row["id"]),
            )
            self._db.execute("COMMIT")
        except Exception:
            self._db.execute("ROLLBACK")
            raise
        payload = json.loads(row["request_json"])
        return LeasedJob(
            id=row["id"],
            request=InferenceRequest(**payload),
            attempts=row["attempts"] + 1,
            max_attempts=row["max_attempts"],
        )

    def complete(self, job_id: str, worker: str, result: dict[str, Any]) -> None:
        changed = self._db.execute(
            """
            UPDATE jobs
            SET status='completed', result_json=?, leased_by=NULL, lease_until=NULL, updated_at=?
            WHERE id=? AND status='running' AND leased_by=?
            """,
            (_canonical(result), self._clock(), job_id, worker),
        ).rowcount
        if changed != 1:
            raise RuntimeError("job lease is not held by this worker")

    def fail(
        self, job: LeasedJob, worker: str, error: str, retry_delay: float = 0
    ) -> None:
        terminal = job.attempts >= job.max_attempts
        changed = self._db.execute(
            """
            UPDATE jobs
            SET status=?, available_at=?, last_error=?, leased_by=NULL, lease_until=NULL, updated_at=?
            WHERE id=? AND status='running' AND leased_by=?
            """,
            (
                "failed" if terminal else "queued",
                self._clock() + max(0, retry_delay),
                error[:1000],
                self._clock(),
                job.id,
                worker,
            ),
        ).rowcount
        if changed != 1:
            raise RuntimeError("job lease is not held by this worker")

    def get(self, job_id: str) -> dict[str, Any]:
        row = self._db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        result = dict(row)
        for key in ("request_json", "result_json"):
            if result[key] is not None:
                result[key.removesuffix("_json")] = json.loads(result.pop(key))
        return result


class EvidenceJournal:
    """Append-only hash chain for local workload evidence."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _last_hash(self) -> str:
        if not self.path.exists():
            return "0" * 64
        lines = [
            line for line in self.path.read_text(encoding="utf-8").splitlines() if line
        ]
        return json.loads(lines[-1])["entry_sha256"] if lines else "0" * 64

    def append(self, event: dict[str, Any]) -> str:
        body = {"previous_sha256": self._last_hash(), "event": event}
        digest = hashlib.sha256(_canonical(body).encode()).hexdigest()
        record = {**body, "entry_sha256": digest}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical(record) + "\n")
        return digest

    def verify(self) -> bool:
        previous = "0" * 64
        if not self.path.exists():
            return True
        for line in self.path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            body = {"previous_sha256": previous, "event": record["event"]}
            if record["previous_sha256"] != previous:
                return False
            if (
                hashlib.sha256(_canonical(body).encode()).hexdigest()
                != record["entry_sha256"]
            ):
                return False
            previous = record["entry_sha256"]
        return True


class WorkloadRunner:
    def __init__(
        self,
        queue: JobQueue,
        provider: FlopProvider,
        journal: EvidenceJournal,
        worker: str = "worker-1",
    ) -> None:
        self.queue = queue
        self.provider = provider
        self.journal = journal
        self.worker = worker

    def run_once(self) -> str | None:
        job = self.queue.lease_next(self.worker)
        if job is None:
            return None
        started = time.perf_counter()
        try:
            session_id = self.provider.submit_inference(job.request)
            result = self.provider.get_session_status(session_id)
            if result.get("status") != "completed":
                raise RuntimeError(
                    f"session ended in {result.get('status', 'unknown')} state"
                )
            result["runner_latency_ms"] = round(
                (time.perf_counter() - started) * 1000, 3
            )
            self.queue.complete(job.id, self.worker, result)
            self.journal.append(
                {
                    "kind": "inference-completed",
                    "job_id": job.id,
                    "request_sha256": job.request.fingerprint(),
                    "result_sha256": hashlib.sha256(
                        _canonical(result).encode()
                    ).hexdigest(),
                    "session_id": session_id,
                    "cost_flop": result.get("cost_flop"),
                    "model": result.get("model"),
                }
            )
            return job.id
        except Exception as error:  # noqa: BLE001 - adapters have provider-specific failures
            self.queue.fail(
                job, self.worker, f"{type(error).__name__}: {error}", retry_delay=1
            )
            self.journal.append(
                {
                    "kind": "inference-attempt-failed",
                    "job_id": job.id,
                    "attempt": job.attempts,
                    "error_type": type(error).__name__,
                }
            )
            return job.id


def validate_activation_document(document: dict[str, Any]) -> None:
    """Fail closed before a future live adapter may be selected.

    The document is operator-supplied evidence, not a network implementation.
    It must name an official source and its captured digest. This function never
    fetches the source, signs anything, or enables a live provider.
    """

    required = {"mode", "source_url", "source_sha256", "confirmed_by_operator"}
    if set(document) != required:
        raise ValueError("activation document has missing or unknown fields")
    if document["mode"] != "testnet" or document["confirmed_by_operator"] is not True:
        raise ValueError("live activation requires explicit testnet confirmation")
    source = urlsplit(document["source_url"])
    official = source.scheme == "https" and (
        source.hostname == "flop.finance"
        or (source.hostname == "github.com" and source.path.startswith("/flop-labs/"))
    )
    if not official:
        raise ValueError("source_url is not an approved official FLOP source")
    digest = document["source_sha256"]
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError("source_sha256 must be a 64-character digest")
    try:
        int(digest, 16)
    except ValueError as error:
        raise ValueError("source_sha256 must be hexadecimal") from error
