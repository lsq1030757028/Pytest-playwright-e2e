from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from ..memory_contracts import ErrorCode, MemoryContractError
from .models import FormationEvent, FormationReplayEvidence


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
    except MemoryContractError:
        raise
    except Exception as exc:
        raise MemoryContractError(
            ErrorCode.INTEGRITY_FAILED,
            "M1C formation/consolidation integrity verification failed",
        ) from exc


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        is not None
    )
