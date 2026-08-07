import sqlite3

import pytest

from test_workflow.memory_contracts import ErrorCode, MemoryContractError, canonical_sha256
from test_workflow.memory_formation import BackgroundConsolidator
from test_workflow.memory_formation.contamination import (
    ContaminationClass,
    MemoryContaminationRegistry,
)
from test_workflow.memory_store import SQLiteMemoryStore
from tests.integration.test_m1c_background_consolidation import _hot_parent, _request


def _mark_hidden_parent(db_path, *, number: int) -> str:
    parent = _hot_parent(db_path, claim="fixture answer 42", number=number)
    MemoryContaminationRegistry(db_path).mark(
        memory_ref=parent,
        contamination_class=ContaminationClass.HIDDEN_HOLDOUT,
        evidence_digest=canonical_sha256({"fixture": f"hidden-{number}"}),
    )
    return parent


def test_tampered_contamination_record_blocks_consolidation(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    parent = _mark_hidden_parent(db_path, number=907)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            UPDATE memory_contamination
            SET evidence_digest = ?
            WHERE memory_ref = ?
            """,
            ("b" * 64, parent),
        )
        connection.commit()

    with pytest.raises(MemoryContractError) as exc:
        BackgroundConsolidator(SQLiteMemoryStore(db_path)).consolidate(
            _request(
                parents=(parent,),
                claim="fixture answer 42",
                subject="tampered-contamination",
                request_id="tampered-contamination",
                idempotency_key="tampered-contamination-idem",
            )
        )
    assert exc.value.code is ErrorCode.INTEGRITY_FAILED


def test_deleted_contamination_record_blocks_consolidation(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    parent = _mark_hidden_parent(db_path, number=908)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "DELETE FROM memory_contamination WHERE memory_ref = ?",
            (parent,),
        )
        connection.commit()

    with pytest.raises(MemoryContractError) as exc:
        BackgroundConsolidator(SQLiteMemoryStore(db_path)).consolidate(
            _request(
                parents=(parent,),
                claim="fixture answer 42",
                subject="deleted-contamination",
                request_id="deleted-contamination",
                idempotency_key="deleted-contamination-idem",
            )
        )
    assert exc.value.code is ErrorCode.INTEGRITY_FAILED
