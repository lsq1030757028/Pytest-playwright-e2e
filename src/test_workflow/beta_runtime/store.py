from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from .models import SubmissionBundle, canonical_json


class JobConflictError(RuntimeError):
    pass


class StaleWriteError(RuntimeError):
    pass


class LeaseError(RuntimeError):
    pass


TERMINAL_STATES = {"SUCCEEDED", "FAILED", "BLOCKED", "CANCELLED", "TIMED_OUT"}


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    idempotency_key: str
    request_fingerprint: str
    state: str
    revision: int
    submission: dict[str, Any]
    result: dict[str, Any] | None
    cancel_requested: bool
    created_at: float
    updated_at: float


@dataclass(frozen=True)
class AttemptLease:
    attempt_id: str
    job_id: str
    lease_token: str
    worker_id: str
    lease_expires_at: float
    command_started: bool


class RuntimeStore:
    SCHEMA_VERSION = 1

    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir.resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.state_dir / "beta-a-runtime.sqlite3"
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.execute("COMMIT")
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._transaction() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runtime_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    request_fingerprint TEXT NOT NULL,
                    submission_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    result_json TEXT,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS job_events (
                    job_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    state TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    PRIMARY KEY (job_id, seq),
                    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
                );
                CREATE TABLE IF NOT EXISTS attempts (
                    attempt_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL UNIQUE,
                    state TEXT NOT NULL,
                    lease_token TEXT,
                    worker_id TEXT,
                    lease_expires_at REAL,
                    command_started INTEGER NOT NULL DEFAULT 0,
                    command_manifest_json TEXT,
                    evidence_manifest_json TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
                );
                """
            )
            existing = connection.execute(
                "SELECT value FROM runtime_meta WHERE key = 'schema_version'"
            ).fetchone()
            if existing is None:
                connection.execute(
                    "INSERT INTO runtime_meta(key, value) VALUES('schema_version', ?)",
                    (str(self.SCHEMA_VERSION),),
                )
            elif int(existing["value"]) != self.SCHEMA_VERSION:
                raise RuntimeError("incompatible BETA-A runtime schema version")

    def submit(self, bundle: SubmissionBundle, *, now: float | None = None) -> tuple[JobRecord, bool]:
        timestamp = time.time() if now is None else now
        key = str(bundle.submission["idempotency_key"])
        payload = bundle.durable_payload()
        with self._transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM jobs WHERE idempotency_key = ?", (key,)
            ).fetchone()
            if existing is not None:
                if existing["request_fingerprint"] != bundle.fingerprint:
                    raise JobConflictError("idempotency key is already bound to a different request")
                return self._row_to_job(existing), False

            job_id = f"job-{uuid.uuid4().hex}"
            connection.execute(
                """
                INSERT INTO jobs(
                    job_id, idempotency_key, request_fingerprint, submission_json,
                    state, revision, created_at, updated_at
                ) VALUES(?, ?, ?, ?, 'ACCEPTED', 0, ?, ?)
                """,
                (job_id, key, bundle.fingerprint, canonical_json(payload), timestamp, timestamp),
            )
            self._append_event(
                connection,
                job_id,
                event_type="JOB_ACCEPTED",
                state="ACCEPTED",
                payload={"request_fingerprint": bundle.fingerprint},
                created_at=timestamp,
            )
            row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            assert row is not None
            return self._row_to_job(row), True

    def get_job(self, job_id: str) -> JobRecord:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        return self._row_to_job(row)

    def events(self, job_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM job_events WHERE job_id = ? ORDER BY seq", (job_id,)
            ).fetchall()
        return [
            {
                "seq": int(row["seq"]),
                "event_type": row["event_type"],
                "state": row["state"],
                "payload": json.loads(row["payload_json"]),
                "created_at": float(row["created_at"]),
            }
            for row in rows
        ]

    def transition(
        self,
        job_id: str,
        *,
        expected_revision: int,
        new_state: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        lease_token: str | None = None,
        now: float | None = None,
    ) -> JobRecord:
        timestamp = time.time() if now is None else now
        with self._transaction() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            if int(row["revision"]) != expected_revision:
                raise StaleWriteError("job revision changed")
            if row["state"] in TERMINAL_STATES:
                raise StaleWriteError("terminal job is immutable")
            if lease_token is not None:
                self._assert_current_lease(connection, job_id, lease_token, timestamp)

            next_revision = expected_revision + 1
            updated = connection.execute(
                """
                UPDATE jobs
                   SET state = ?, revision = ?, result_json = ?, updated_at = ?
                 WHERE job_id = ? AND revision = ?
                """,
                (
                    new_state,
                    next_revision,
                    canonical_json(result) if result is not None else row["result_json"],
                    timestamp,
                    job_id,
                    expected_revision,
                ),
            )
            if updated.rowcount != 1:
                raise StaleWriteError("job revision changed")
            self._append_event(
                connection,
                job_id,
                event_type=event_type,
                state=new_state,
                payload=payload or {},
                created_at=timestamp,
            )
            changed = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            assert changed is not None
            return self._row_to_job(changed)

    def request_cancel(self, job_id: str, *, now: float | None = None) -> JobRecord:
        timestamp = time.time() if now is None else now
        with self._transaction() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            if row["state"] in TERMINAL_STATES or bool(row["cancel_requested"]):
                return self._row_to_job(row)
            connection.execute(
                "UPDATE jobs SET cancel_requested = 1, updated_at = ? WHERE job_id = ?",
                (timestamp, job_id),
            )
            self._append_event(
                connection,
                job_id,
                event_type="CANCEL_REQUESTED",
                state=row["state"],
                payload={},
                created_at=timestamp,
            )
            changed = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            assert changed is not None
            return self._row_to_job(changed)

    def is_cancel_requested(self, job_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT cancel_requested FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        if row is None:
            raise KeyError(job_id)
        return bool(row["cancel_requested"])

    def claim_ready(
        self,
        *,
        worker_id: str,
        now: float,
        lease_ttl_seconds: float = 10.0,
    ) -> tuple[JobRecord, AttemptLease] | None:
        with self._transaction() as connection:
            row = connection.execute(
                """
                SELECT * FROM jobs
                 WHERE state = 'READY_TO_EXECUTE' AND cancel_requested = 0
                 ORDER BY created_at, job_id
                 LIMIT 1
                """
            ).fetchone()
            if row is None:
                return None
            attempt = connection.execute(
                "SELECT * FROM attempts WHERE job_id = ?", (row["job_id"],)
            ).fetchone()
            if attempt is not None:
                if bool(attempt["command_started"]):
                    return None
                expires = attempt["lease_expires_at"]
                if expires is not None and float(expires) > now:
                    return None
                attempt_id = attempt["attempt_id"]
            else:
                attempt_id = f"attempt-{uuid.uuid4().hex}"

            lease_token = f"lease-{uuid.uuid4().hex}"
            expires_at = now + lease_ttl_seconds
            if attempt is None:
                connection.execute(
                    """
                    INSERT INTO attempts(
                        attempt_id, job_id, state, lease_token, worker_id,
                        lease_expires_at, created_at, updated_at
                    ) VALUES(?, ?, 'LEASED', ?, ?, ?, ?, ?)
                    """,
                    (attempt_id, row["job_id"], lease_token, worker_id, expires_at, now, now),
                )
            else:
                connection.execute(
                    """
                    UPDATE attempts
                       SET state = 'LEASED', lease_token = ?, worker_id = ?,
                           lease_expires_at = ?, updated_at = ?
                     WHERE attempt_id = ?
                    """,
                    (lease_token, worker_id, expires_at, now, attempt_id),
                )

            next_revision = int(row["revision"]) + 1
            connection.execute(
                "UPDATE jobs SET state = 'EXECUTING', revision = ?, updated_at = ? WHERE job_id = ?",
                (next_revision, now, row["job_id"]),
            )
            self._append_event(
                connection,
                row["job_id"],
                event_type="ATTEMPT_LEASED",
                state="EXECUTING",
                payload={"attempt_id": attempt_id, "worker_id": worker_id},
                created_at=now,
            )
            job_row = connection.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (row["job_id"],)
            ).fetchone()
            assert job_row is not None
            return self._row_to_job(job_row), AttemptLease(
                attempt_id=attempt_id,
                job_id=row["job_id"],
                lease_token=lease_token,
                worker_id=worker_id,
                lease_expires_at=expires_at,
                command_started=False,
            )

    def heartbeat(
        self,
        lease: AttemptLease,
        *,
        now: float,
        lease_ttl_seconds: float = 10.0,
    ) -> AttemptLease:
        with self._transaction() as connection:
            self._assert_current_lease(connection, lease.job_id, lease.lease_token, now)
            expires_at = now + lease_ttl_seconds
            connection.execute(
                "UPDATE attempts SET lease_expires_at = ?, updated_at = ? WHERE attempt_id = ?",
                (expires_at, now, lease.attempt_id),
            )
        return AttemptLease(
            attempt_id=lease.attempt_id,
            job_id=lease.job_id,
            lease_token=lease.lease_token,
            worker_id=lease.worker_id,
            lease_expires_at=expires_at,
            command_started=lease.command_started,
        )

    def mark_command_started(
        self,
        lease: AttemptLease,
        command_manifest: dict[str, Any],
        *,
        now: float,
    ) -> AttemptLease:
        with self._transaction() as connection:
            attempt = self._assert_current_lease(connection, lease.job_id, lease.lease_token, now)
            if bool(attempt["command_started"]):
                raise LeaseError("command already started for this BETA-A attempt")
            connection.execute(
                """
                UPDATE attempts
                   SET command_started = 1, state = 'RUNNING', command_manifest_json = ?, updated_at = ?
                 WHERE attempt_id = ?
                """,
                (canonical_json(command_manifest), now, lease.attempt_id),
            )
        return AttemptLease(
            attempt_id=lease.attempt_id,
            job_id=lease.job_id,
            lease_token=lease.lease_token,
            worker_id=lease.worker_id,
            lease_expires_at=lease.lease_expires_at,
            command_started=True,
        )

    def set_attempt_evidence(
        self,
        lease: AttemptLease,
        evidence_manifest: dict[str, Any],
        *,
        state: str,
        now: float,
    ) -> None:
        with self._transaction() as connection:
            self._assert_current_lease(connection, lease.job_id, lease.lease_token, now)
            connection.execute(
                """
                UPDATE attempts
                   SET state = ?, evidence_manifest_json = ?, updated_at = ?
                 WHERE attempt_id = ?
                """,
                (state, canonical_json(evidence_manifest), now, lease.attempt_id),
            )

    def reconcile_uncertain(self, *, now: float | None = None) -> list[str]:
        timestamp = time.time() if now is None else now
        blocked: list[str] = []
        with self._transaction() as connection:
            rows = connection.execute(
                """
                SELECT j.*, a.attempt_id, a.command_started, a.state AS attempt_state
                  FROM jobs j JOIN attempts a ON a.job_id = j.job_id
                 WHERE j.state = 'EXECUTING' AND a.command_started = 1
                   AND a.state NOT IN ('COMPLETED', 'FAILED', 'CANCELLED', 'TIMED_OUT')
                """
            ).fetchall()
            for row in rows:
                result = {
                    "verdict": "INSUFFICIENT_EVIDENCE",
                    "reason": "ABANDONED_UNCERTAIN",
                    "attempt_id": row["attempt_id"],
                    "automatic_reexecution": False,
                }
                connection.execute(
                    "UPDATE attempts SET state = 'ABANDONED_UNCERTAIN', updated_at = ? WHERE attempt_id = ?",
                    (timestamp, row["attempt_id"]),
                )
                next_revision = int(row["revision"]) + 1
                connection.execute(
                    """
                    UPDATE jobs
                       SET state = 'BLOCKED', revision = ?, result_json = ?, updated_at = ?
                     WHERE job_id = ?
                    """,
                    (next_revision, canonical_json(result), timestamp, row["job_id"]),
                )
                self._append_event(
                    connection,
                    row["job_id"],
                    event_type="UNCERTAIN_EXECUTION_BLOCKED",
                    state="BLOCKED",
                    payload=result,
                    created_at=timestamp,
                )
                blocked.append(row["job_id"])
        return blocked

    def attempt_for_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM attempts WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return dict(row)

    def _assert_current_lease(
        self,
        connection: sqlite3.Connection,
        job_id: str,
        lease_token: str,
        now: float,
    ) -> sqlite3.Row:
        attempt = connection.execute(
            "SELECT * FROM attempts WHERE job_id = ?", (job_id,)
        ).fetchone()
        if attempt is None or attempt["lease_token"] != lease_token:
            raise LeaseError("stale worker lease")
        expires = attempt["lease_expires_at"]
        if expires is None or float(expires) <= now:
            raise LeaseError("expired worker lease")
        return attempt

    def _append_event(
        self,
        connection: sqlite3.Connection,
        job_id: str,
        *,
        event_type: str,
        state: str,
        payload: dict[str, Any],
        created_at: float,
    ) -> None:
        row = connection.execute(
            "SELECT COALESCE(MAX(seq), 0) AS seq FROM job_events WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        seq = int(row["seq"]) + 1
        connection.execute(
            """
            INSERT INTO job_events(job_id, seq, event_type, state, payload_json, created_at)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (job_id, seq, event_type, state, canonical_json(payload), created_at),
        )

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> JobRecord:
        return JobRecord(
            job_id=row["job_id"],
            idempotency_key=row["idempotency_key"],
            request_fingerprint=row["request_fingerprint"],
            state=row["state"],
            revision=int(row["revision"]),
            submission=json.loads(row["submission_json"]),
            result=json.loads(row["result_json"]) if row["result_json"] else None,
            cancel_requested=bool(row["cancel_requested"]),
            created_at=float(row["created_at"]),
            updated_at=float(row["updated_at"]),
        )
