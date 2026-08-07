from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..memory_contracts import MemoryRevision, canonical_sha256

_TOKEN_RE = re.compile(r"[\w.-]+", re.UNICODE)


@dataclass(frozen=True)
class IndexHit:
    ref: str
    rank: int
    score: int


class SQLiteDerivedIndex:
    """Replaceable metadata/keyword index derived from the authoritative Store.

    The index never decides authority. Callers must pass an already authorized
    and lifecycle-valid ref set, and every released result must be revalidated
    against the primary Store.
    """

    profile_version = "sqlite-derived-index@1"

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.db_path,
            timeout=5.0,
            isolation_level=None,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS search_index (
                    revision_id TEXT PRIMARY KEY,
                    memory_id TEXT NOT NULL,
                    memory_ref TEXT NOT NULL UNIQUE,
                    namespace TEXT NOT NULL,
                    memory_kind TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    tokens_json TEXT NOT NULL,
                    source_sequence INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_search_index_namespace
                    ON search_index(namespace, created_at, memory_ref);
                CREATE INDEX IF NOT EXISTS idx_search_index_memory
                    ON search_index(memory_id);
                """
            )

    @staticmethod
    def _flatten_strings(value: Any) -> Iterable[str]:
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for key, item in value.items():
                yield key
                yield from SQLiteDerivedIndex._flatten_strings(item)
        elif isinstance(value, (list, tuple, set, frozenset)):
            for item in value:
                yield from SQLiteDerivedIndex._flatten_strings(item)

    @classmethod
    def _tokens(cls, revision: MemoryRevision) -> tuple[str, ...]:
        tokens: set[str] = set()
        for text in cls._flatten_strings(revision.content):
            tokens.update(match.group(0).casefold() for match in _TOKEN_RE.finditer(text))
        return tuple(sorted(tokens))

    def apply_pending(self, *, limit: int = 256) -> int:
        """Apply primary outbox events idempotently in one index transaction."""
        if limit < 1:
            raise ValueError("limit must be positive")
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                rows = connection.execute(
                    """
                    SELECT sequence, event_type, memory_id, payload_json
                    FROM outbox
                    WHERE applied = 0
                    ORDER BY sequence
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
                for row in rows:
                    event_type = row["event_type"]
                    if event_type == "REVISION_COMMITTED":
                        payload = json.loads(row["payload_json"])
                        revision_row = connection.execute(
                            "SELECT payload_json FROM revisions WHERE revision_id = ?",
                            (payload["revision_id"],),
                        ).fetchone()
                        if revision_row is None:
                            # Physical Forget may have removed the primary row before
                            # the derived index catches up. The primary Store wins.
                            if row["memory_id"] is not None:
                                connection.execute(
                                    "DELETE FROM search_index WHERE memory_id = ?",
                                    (row["memory_id"],),
                                )
                        else:
                            revision = MemoryRevision.model_validate_json(
                                revision_row["payload_json"]
                            )
                            connection.execute(
                                """
                                INSERT INTO search_index(
                                    revision_id, memory_id, memory_ref, namespace,
                                    memory_kind, schema_version, created_at,
                                    content_hash, tokens_json, source_sequence
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                ON CONFLICT(revision_id) DO UPDATE SET
                                    memory_id = excluded.memory_id,
                                    memory_ref = excluded.memory_ref,
                                    namespace = excluded.namespace,
                                    memory_kind = excluded.memory_kind,
                                    schema_version = excluded.schema_version,
                                    created_at = excluded.created_at,
                                    content_hash = excluded.content_hash,
                                    tokens_json = excluded.tokens_json,
                                    source_sequence = excluded.source_sequence
                                """,
                                (
                                    revision.revision_id,
                                    revision.memory_id,
                                    revision.ref,
                                    revision.namespace.canonical,
                                    revision.memory_kind.value,
                                    revision.schema_version,
                                    revision.created_at.isoformat(),
                                    revision.content_hash,
                                    json.dumps(self._tokens(revision), ensure_ascii=False),
                                    row["sequence"],
                                ),
                            )
                    elif event_type == "FORGET_COMMITTED" and row["memory_id"] is not None:
                        connection.execute(
                            "DELETE FROM search_index WHERE memory_id = ?",
                            (row["memory_id"],),
                        )
                    connection.execute(
                        "UPDATE outbox SET applied = 1 WHERE sequence = ?",
                        (row["sequence"],),
                    )
                connection.commit()
                return len(rows)
            except Exception:
                connection.rollback()
                raise

    def pending_count(self) -> int:
        with closing(self._connect()) as connection:
            return int(
                connection.execute(
                    "SELECT COUNT(*) FROM outbox WHERE applied = 0"
                ).fetchone()[0]
            )

    def _rows_for_refs(self, refs: tuple[str, ...]) -> tuple[sqlite3.Row, ...]:
        if not refs:
            return ()
        placeholders = ",".join("?" for _ in refs)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT memory_ref, memory_kind, schema_version, created_at,
                       content_hash, tokens_json, source_sequence
                FROM search_index
                WHERE memory_ref IN ({placeholders})
                """,
                refs,
            ).fetchall()
        return tuple(rows)

    def metadata_rank(
        self,
        *,
        eligible_refs: tuple[str, ...],
        memory_kind: str | None = None,
        schema_version: str | None = None,
    ) -> tuple[IndexHit, ...]:
        rows = [
            row
            for row in self._rows_for_refs(eligible_refs)
            if (memory_kind is None or row["memory_kind"] == memory_kind)
            and (schema_version is None or row["schema_version"] == schema_version)
        ]
        rows.sort(key=lambda row: (row["created_at"], row["memory_ref"]), reverse=True)
        return tuple(
            IndexHit(ref=row["memory_ref"], rank=rank, score=1)
            for rank, row in enumerate(rows, start=1)
        )

    def keyword_rank(
        self,
        *,
        eligible_refs: tuple[str, ...],
        keywords: tuple[str, ...],
    ) -> tuple[IndexHit, ...]:
        normalized = {keyword.casefold() for keyword in keywords if keyword.strip()}
        if not normalized:
            return ()
        scored: list[tuple[int, str, str]] = []
        for row in self._rows_for_refs(eligible_refs):
            tokens = set(json.loads(row["tokens_json"]))
            matched = len(tokens & normalized)
            if matched:
                scored.append((matched, row["created_at"], row["memory_ref"]))
        scored.sort(key=lambda item: (-item[0], item[1], item[2]), reverse=False)
        # Keep newest first for equal keyword coverage while retaining deterministic refs.
        grouped = sorted(scored, key=lambda item: (-item[0], -_time_key(item[1]), item[2]))
        return tuple(
            IndexHit(ref=ref, rank=rank, score=matched)
            for rank, (matched, _created_at, ref) in enumerate(grouped, start=1)
        )

    def archive_rank(self, *, eligible_refs: tuple[str, ...]) -> tuple[IndexHit, ...]:
        rows = list(self._rows_for_refs(eligible_refs))
        rows.sort(key=lambda row: (row["created_at"], row["memory_ref"]))
        return tuple(
            IndexHit(ref=row["memory_ref"], rank=rank, score=1)
            for rank, row in enumerate(rows, start=1)
        )

    def snapshot_digest(self, *, eligible_refs: tuple[str, ...]) -> str:
        rows = self._rows_for_refs(eligible_refs)
        payload = [
            {
                "ref": row["memory_ref"],
                "content_hash": row["content_hash"],
                "source_sequence": row["source_sequence"],
                "profile": self.profile_version,
            }
            for row in sorted(rows, key=lambda item: item["memory_ref"])
        ]
        return canonical_sha256(payload)

    def contains_ref(self, ref: str) -> bool:
        with closing(self._connect()) as connection:
            return (
                connection.execute(
                    "SELECT 1 FROM search_index WHERE memory_ref = ?",
                    (ref,),
                ).fetchone()
                is not None
            )


def _time_key(value: str) -> float:
    from datetime import datetime

    return datetime.fromisoformat(value).timestamp()
