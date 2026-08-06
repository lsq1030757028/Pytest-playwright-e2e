from json import loads
from pathlib import Path

from jsonschema import Draft202012Validator

SCHEMA_DIR = Path(".agent/relay/schemas")


def registry() -> dict[str, object]:
    return {
        "schema_version": 1,
        "control_id": "PARALLEL-WORK-CLAIMS",
        "enabled": False,
        "revision": 0,
        "claim_sequence": 0,
        "claims": {},
        "recovered_claims": [],
        "integration_queue": [],
    }


def test_registry_schema_accepts_active_and_recovered_claims() -> None:
    schema = loads((SCHEMA_DIR / "work-claims.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    active_claim = {
        "work_item_id": "A",
        "claim_token": "claim-a-1-20260806T120000Z",
        "surface": "HUMAN_CONTROL",
        "state": "IN_PROGRESS",
        "exclusive_domain": "alpha",
        "target_branch": "branch-a",
        "target_pr": 57,
        "expected_head_sha": "a" * 40,
        "started_at": "2026-08-06T12:00:00Z",
        "heartbeat_at": "2026-08-06T12:10:00Z",
        "expires_at": "2026-08-06T14:10:00Z",
        "last_checkpoint": "TESTS_GREEN",
    }
    recovered_claim = {
        **active_claim,
        "state": "STALE_RECOVERED",
        "recovered_at": "2026-08-06T15:00:00Z",
    }
    document = registry()
    document["claims"] = {"A": active_claim}
    document["recovered_claims"] = [recovered_claim]
    validator.validate(document)


def test_registry_schema_rejects_recovery_without_recovery_time() -> None:
    schema = loads((SCHEMA_DIR / "work-claims.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    recovered_claim = {
        "work_item_id": "A",
        "claim_token": "claim-a-1-20260806T120000Z",
        "surface": "HUMAN_CONTROL",
        "state": "STALE_RECOVERED",
        "exclusive_domain": "alpha",
        "target_branch": "branch-a",
        "target_pr": None,
        "expected_head_sha": "a" * 40,
        "started_at": "2026-08-06T12:00:00Z",
        "heartbeat_at": "2026-08-06T12:10:00Z",
        "expires_at": "2026-08-06T14:10:00Z",
        "last_checkpoint": "ABANDONED",
    }
    document = registry()
    document["recovered_claims"] = [recovered_claim]
    errors = list(validator.iter_errors(document))
    assert any("recovered_at" in error.message for error in errors)


def test_integration_lease_schema_accepts_idle_and_active_states() -> None:
    schema = loads((SCHEMA_DIR / "integration-lease.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    validator.validate(
        {
            "schema_version": 1,
            "revision": 0,
            "sequence": 0,
            "status": "IDLE",
            "integration_token": None,
            "work_item_id": None,
            "started_at": None,
            "expires_at": None,
        }
    )
    validator.validate(
        {
            "schema_version": 1,
            "revision": 1,
            "sequence": 1,
            "status": "ACTIVE",
            "integration_token": "integration-1-20260806T120000Z",
            "work_item_id": "A",
            "started_at": "2026-08-06T12:00:00Z",
            "expires_at": "2026-08-06T13:00:00Z",
        }
    )
