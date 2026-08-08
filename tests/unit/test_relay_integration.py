from datetime import UTC, datetime, timedelta

import pytest

from test_workflow.relay_claims import RegistryRevisionConflict
from test_workflow.relay_integration import recover_stale_integration_lease

NOW = datetime(2026, 8, 8, 6, 30, tzinfo=UTC)


def active_lease(*, expires_at: datetime, revision: int = 21) -> dict[str, object]:
    return {
        "schema_version": 1,
        "revision": revision,
        "sequence": 5,
        "status": "ACTIVE",
        "integration_token": "m1b-spec-integration-5",
        "work_item_id": "M1B-STORE-RETRIEVAL-SPEC",
        "started_at": "2026-08-07T02:59:30Z",
        "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
    }


def test_expired_integration_lease_recovers_to_idle_without_activity() -> None:
    lease = active_lease(expires_at=NOW - timedelta(hours=1))

    recovered, work_item_id, protected = recover_stale_integration_lease(
        lease,
        expected_revision=21,
        now=NOW,
        activity={},
    )

    assert work_item_id == "M1B-STORE-RETRIEVAL-SPEC"
    assert protected is False
    assert recovered["revision"] == 22
    assert recovered["status"] == "IDLE"
    assert recovered["integration_token"] is None
    assert recovered["work_item_id"] is None
    assert recovered["started_at"] is None
    assert recovered["expires_at"] is None


def test_expired_integration_lease_is_protected_by_active_ci() -> None:
    lease = active_lease(expires_at=NOW - timedelta(minutes=1))

    recovered, work_item_id, protected = recover_stale_integration_lease(
        lease,
        expected_revision=21,
        now=NOW,
        activity={"active_ci": True},
    )

    assert recovered == lease
    assert work_item_id is None
    assert protected is True


def test_unexpired_integration_lease_is_not_recovered() -> None:
    lease = active_lease(expires_at=NOW + timedelta(minutes=30))

    recovered, work_item_id, protected = recover_stale_integration_lease(
        lease,
        expected_revision=21,
        now=NOW,
        activity={},
    )

    assert recovered == lease
    assert work_item_id is None
    assert protected is False


def test_integration_lease_recovery_is_revision_fenced() -> None:
    lease = active_lease(expires_at=NOW - timedelta(minutes=1))

    with pytest.raises(RegistryRevisionConflict):
        recover_stale_integration_lease(
            lease,
            expected_revision=20,
            now=NOW,
            activity={},
        )
