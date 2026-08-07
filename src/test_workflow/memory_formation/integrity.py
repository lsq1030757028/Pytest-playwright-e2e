from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from ..memory_contracts import ErrorCode, MemoryContractError
from .models import FormationEvent, FormationReplayEvidence, FormationResult


def verify_formation_integrity(db_path: Path | str) -> None:
    path = Path(db_path)
    try:
        with closing(sqlite3.connect(path)) as connection:
            connection.row_factory = sqlite3.Row
            if _table_exists(connection, "formation_events"):
                for row in connection.execute(
                    """
                    SELECT event_hash, payload_json
                    FROM formation_events
                    ORDER BY event_id
                    """
                ):
                    event = FormationEvent.model_validate_json(row["payload_json"])
                    if event.event_hash != row["event_hash"]:
                        raise ValueError("formation event column/hash mismatch")
            if _table_exists(connection, "formation_replay"):
                for row in connection.execute(
                    """
                    SELECT manifest_digest, payload_json
                    FROM formation_replay
                    ORDER BY request_digest
                    """
                ):
                    evidence = FormationReplayEvidence.model_validate_json(
                        row["payload_json"]
                    )
                    if evidence.manifest_digest != row["manifest_digest"]:
                        raise ValueError("formation replay column/manifest mismatch")
            if all(
                _table_exists(connection, table)
                for table in (
                    "formation_idempotency",
                    "formation_events",
                    "formation_replay",
                )
            ):
                _verify_completed_formation_links(connection)

            if _table_exists(connection, "consolidation_events"):
                # Lazy import avoids a module cycle while preserving model-level
                # event hash validation.
                from .consolidation import ConsolidationEvent

                for row in connection.execute(
                    """
                    SELECT event_hash, payload_json
                    FROM consolidation_events
                    ORDER BY event_id
                    """
                ):
                    event = ConsolidationEvent.model_validate_json(row["payload_json"])
                    if event.event_hash != row["event_hash"]:
                        raise ValueError("consolidation event column/hash mismatch")
            if _table_exists(connection, "consolidation_replay"):
                from .consolidation import ConsolidationReplayEvidence

                for row in connection.execute(
                    """
                    SELECT manifest_digest, payload_json
                    FROM consolidation_replay
                    ORDER BY request_digest
                    """
                ):
                    evidence = ConsolidationReplayEvidence.model_validate_json(
                        row["payload_json"]
                    )
                    if evidence.manifest_digest != row["manifest_digest"]:
                        raise ValueError("consolidation replay column/manifest mismatch")
            if all(
                _table_exists(connection, table)
                for table in (
                    "consolidation_idempotency",
                    "consolidation_events",
                    "consolidation_replay",
                )
            ):
                _verify_completed_consolidation_links(connection)
    except MemoryContractError:
        raise
    except Exception as exc:
        raise MemoryContractError(
            ErrorCode.INTEGRITY_FAILED,
            "M1C formation/consolidation integrity verification failed",
        ) from exc


def _verify_completed_formation_links(connection: sqlite3.Connection) -> None:
    for row in connection.execute(
        """
        SELECT request_digest, result_json
        FROM formation_idempotency
        WHERE state = 'DONE' AND result_json IS NOT NULL
        ORDER BY idempotency_key
        """
    ):
        result = FormationResult.model_validate_json(row["result_json"])
        if result.request_digest != row["request_digest"]:
            raise ValueError("formation idempotency/result request mismatch")
        event_row = connection.execute(
            "SELECT 1 FROM formation_events WHERE event_id = ?",
            (result.formation_event_ref,),
        ).fetchone()
        if event_row is None:
            raise ValueError("completed formation is missing its durable event")
        replay_row = connection.execute(
            """
            SELECT manifest_digest
            FROM formation_replay
            WHERE request_digest = ?
            """,
            (result.request_digest,),
        ).fetchone()
        if (
            replay_row is None
            or replay_row["manifest_digest"] != result.replay_evidence_digest
        ):
            raise ValueError("completed formation is missing its replay evidence")


def _verify_completed_consolidation_links(connection: sqlite3.Connection) -> None:
    from .consolidation import ConsolidationResult

    for row in connection.execute(
        """
        SELECT request_digest, result_json
        FROM consolidation_idempotency
        WHERE state = 'DONE' AND result_json IS NOT NULL
        ORDER BY idempotency_key
        """
    ):
        result = ConsolidationResult.model_validate_json(row["result_json"])
        if result.request_digest != row["request_digest"]:
            raise ValueError("consolidation idempotency/result request mismatch")
        event_row = connection.execute(
            "SELECT 1 FROM consolidation_events WHERE event_id = ?",
            (result.consolidation_event_ref,),
        ).fetchone()
        if event_row is None:
            raise ValueError("completed consolidation is missing its durable event")
        replay_row = connection.execute(
            """
            SELECT manifest_digest
            FROM consolidation_replay
            WHERE request_digest = ?
            """,
            (result.request_digest,),
        ).fetchone()
        if (
            replay_row is None
            or replay_row["manifest_digest"] != result.replay_evidence_digest
        ):
            raise ValueError("completed consolidation is missing its replay evidence")


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        is not None
    )
