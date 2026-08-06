from datetime import datetime, timedelta, timezone

import pytest

from test_workflow.relay_claims import (
    AllocatorDisabled,
    ClaimControlError,
    ClaimFenceViolation,
    NoClaimableWork,
    RegistryRevisionConflict,
    acquire_integration_lease,
    allocate_next,
    assert_claim_fence,
    enqueue_integration,
    heartbeat_claim,
    recover_stale_claims,
    select_integration_entry,
    select_work_item,
    validate_work_map,
)

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)


def work_item(
    work_item_id: str,
    *,
    priority: int,
    domain: str,
    branch: str,
    state: str = "READY",
    dependencies: list[str] | None = None,
    target_pr: int | None = None,
) -> dict[str, object]:
    return {
        "work_item_id": work_item_id,
        "state": state,
        "priority": priority,
        "dependencies": dependencies or [],
        "authority_issue": 55,
        "required_spec": "SPEC",
        "target_branch": branch,
        "target_pr": target_pr,
        "exclusive_domain": domain,
        "integration_group": "GROUP",
    }


def work_map(*items: dict[str, object]) -> dict[str, object]:
    return {
        "integration_groups": {"GROUP": {"verification": "test"}},
        "domain_incompatibilities": {},
        "work_items": list(items),
    }


def registry(*, enabled: bool = True) -> dict[str, object]:
    return {
        "schema_version": 1,
        "control_id": "PARALLEL-WORK-CLAIMS",
        "enabled": enabled,
        "revision": 0,
        "claim_sequence": 0,
        "claims": {},
        "recovered_claims": [],
        "integration_queue": [],
    }


def allocate(
    mapping: dict[str, object],
    state: dict[str, object],
    *,
    branch_heads: dict[str, str],
):
    return allocate_next(
        mapping,
        state,
        expected_revision=state["revision"],
        surface="HUMAN_CONTROL",
        now=NOW,
        branch_heads=branch_heads,
    )


def test_selection_is_priority_then_stable_id() -> None:
    mapping = work_map(
        work_item("B", priority=100, domain="b", branch="branch-b"),
        work_item("A", priority=100, domain="a", branch="branch-a"),
        work_item("C", priority=90, domain="c", branch="branch-c"),
    )
    assert select_work_item(mapping, registry()).work_item_id == "A"


def test_two_independent_domains_can_be_claimed_concurrently() -> None:
    mapping = work_map(
        work_item("A", priority=100, domain="alpha", branch="branch-a"),
        work_item("B", priority=90, domain="beta", branch="branch-b"),
    )
    first = allocate(mapping, registry(), branch_heads={"branch-a": "a1", "branch-b": "b1"})
    second = allocate(
        mapping,
        first.registry,
        branch_heads={"branch-a": "a1", "branch-b": "b1"},
    )
    assert {first.claim["work_item_id"], second.claim["work_item_id"]} == {"A", "B"}
    assert len(second.registry["claims"]) == 2


def test_same_domain_is_rejected() -> None:
    mapping = work_map(
        work_item("A", priority=100, domain="shared", branch="branch-a"),
        work_item("B", priority=90, domain="shared", branch="branch-b"),
    )
    first = allocate(mapping, registry(), branch_heads={"branch-a": "a1", "branch-b": "b1"})
    with pytest.raises(NoClaimableWork) as error:
        allocate(mapping, first.registry, branch_heads={"branch-a": "a1", "branch-b": "b1"})
    assert error.value.rejected["B"] == "domain_conflict:shared"


def test_same_branch_is_rejected_even_with_different_domains() -> None:
    mapping = work_map(
        work_item("A", priority=100, domain="alpha", branch="shared-branch"),
        work_item("B", priority=90, domain="beta", branch="shared-branch"),
    )
    first = allocate(mapping, registry(), branch_heads={"shared-branch": "h1"})
    with pytest.raises(NoClaimableWork) as error:
        allocate(mapping, first.registry, branch_heads={"shared-branch": "h1"})
    assert error.value.rejected["B"] == "branch_conflict:shared-branch"


def test_dependency_must_be_closed() -> None:
    mapping = work_map(
        work_item("A", priority=100, domain="alpha", branch="branch-a", state="IN_PROGRESS"),
        work_item(
            "B",
            priority=90,
            domain="beta",
            branch="branch-b",
            dependencies=["A"],
        ),
    )
    result = select_work_item(mapping, registry())
    assert result.work_item_id is None
    assert result.rejected["B"] == "dependencies:A"


def test_registry_revision_is_cas_fenced() -> None:
    mapping = work_map(work_item("A", priority=100, domain="alpha", branch="branch-a"))
    with pytest.raises(RegistryRevisionConflict):
        allocate_next(
            mapping,
            registry(),
            expected_revision=1,
            surface="RELAY_RUNTIME",
            now=NOW,
            branch_heads={"branch-a": "a1"},
        )


def test_disabled_allocator_fails_closed() -> None:
    mapping = work_map(work_item("A", priority=100, domain="alpha", branch="branch-a"))
    with pytest.raises(AllocatorDisabled):
        allocate(mapping, registry(enabled=False), branch_heads={"branch-a": "a1"})


def test_mutation_fence_checks_token_branch_head_and_expiry() -> None:
    mapping = work_map(work_item("A", priority=100, domain="alpha", branch="branch-a"))
    allocation = allocate(mapping, registry(), branch_heads={"branch-a": "a1"})
    assert_claim_fence(
        allocation.registry,
        work_item_id="A",
        claim_token=allocation.claim["claim_token"],
        exclusive_domain="alpha",
        target_branch="branch-a",
        actual_head_sha="a1",
        now=NOW,
    )
    with pytest.raises(ClaimFenceViolation, match="expected_head_sha"):
        assert_claim_fence(
            allocation.registry,
            work_item_id="A",
            claim_token=allocation.claim["claim_token"],
            exclusive_domain="alpha",
            target_branch="branch-a",
            actual_head_sha="unexpected",
            now=NOW,
        )
    with pytest.raises(ClaimFenceViolation, match="expired"):
        assert_claim_fence(
            allocation.registry,
            work_item_id="A",
            claim_token=allocation.claim["claim_token"],
            exclusive_domain="alpha",
            target_branch="branch-a",
            actual_head_sha="a1",
            now=NOW + timedelta(hours=3),
        )


def test_heartbeat_advances_revision_and_checkpoint() -> None:
    mapping = work_map(work_item("A", priority=100, domain="alpha", branch="branch-a"))
    allocation = allocate(mapping, registry(), branch_heads={"branch-a": "a1"})
    updated = heartbeat_claim(
        allocation.registry,
        expected_revision=allocation.registry["revision"],
        work_item_id="A",
        claim_token=allocation.claim["claim_token"],
        now=NOW + timedelta(minutes=30),
        checkpoint="TESTS_GREEN",
    )
    assert updated["revision"] == allocation.registry["revision"] + 1
    assert updated["claims"]["A"]["state"] == "IN_PROGRESS"
    assert updated["claims"]["A"]["last_checkpoint"] == "TESTS_GREEN"


def test_stale_recovery_protects_active_ci_and_recovers_abandoned_claim() -> None:
    mapping = work_map(
        work_item("A", priority=100, domain="alpha", branch="branch-a"),
        work_item("B", priority=90, domain="beta", branch="branch-b"),
    )
    first = allocate(mapping, registry(), branch_heads={"branch-a": "a1", "branch-b": "b1"})
    second = allocate(
        mapping,
        first.registry,
        branch_heads={"branch-a": "a1", "branch-b": "b1"},
    )
    recovered_registry, recovered, protected = recover_stale_claims(
        second.registry,
        expected_revision=second.registry["revision"],
        now=NOW + timedelta(hours=3),
        activity={"A": {}, "B": {"active_ci": True}},
    )
    assert recovered == ["A"]
    assert protected == ["B"]
    assert "A" not in recovered_registry["claims"]
    assert recovered_registry["claims"]["B"]["work_item_id"] == "B"


def test_integration_queue_orders_repairs_then_dependency_unblocking_then_age() -> None:
    mapping = work_map(
        work_item("A", priority=100, domain="alpha", branch="branch-a"),
        work_item("B", priority=90, domain="beta", branch="branch-b"),
    )
    first = allocate(mapping, registry(), branch_heads={"branch-a": "a1", "branch-b": "b1"})
    second = allocate(
        mapping,
        first.registry,
        branch_heads={"branch-a": "a1", "branch-b": "b1"},
    )
    second.registry["claims"]["A"]["state"] = "EVIDENCE_READY"
    second.registry["claims"]["B"]["state"] = "EVIDENCE_READY"
    queued_a = enqueue_integration(
        second.registry,
        expected_revision=second.registry["revision"],
        work_item_id="A",
        claim_token=second.registry["claims"]["A"]["claim_token"],
        now=NOW,
    )
    queued_b = enqueue_integration(
        queued_a,
        expected_revision=queued_a["revision"],
        work_item_id="B",
        claim_token=queued_a["claims"]["B"]["claim_token"],
        now=NOW + timedelta(minutes=1),
        security_or_correctness_repair=True,
    )
    assert select_integration_entry(queued_b)["work_item_id"] == "B"


def test_integration_lease_has_one_holder() -> None:
    state = registry()
    state["integration_queue"] = [
        {
            "work_item_id": "A",
            "claim_token": "claim-a",
            "enqueued_at": NOW.isoformat().replace("+00:00", "Z"),
            "security_or_correctness_repair": False,
            "dependency_unblocking": True,
            "state": "INTEGRATION_WAITING",
        }
    ]
    lease = {"schema_version": 1, "revision": 0, "sequence": 0, "status": "IDLE"}
    acquired = acquire_integration_lease(
        lease,
        state,
        expected_revision=0,
        now=NOW,
    )
    assert acquired["status"] == "ACTIVE"
    assert acquired["work_item_id"] == "A"
    with pytest.raises(ClaimControlError, match="busy"):
        acquire_integration_lease(
            acquired,
            state,
            expected_revision=acquired["revision"],
            now=NOW,
        )


def test_work_map_rejects_cycles() -> None:
    mapping = work_map(
        work_item("A", priority=100, domain="alpha", branch="branch-a", dependencies=["B"]),
        work_item("B", priority=90, domain="beta", branch="branch-b", dependencies=["A"]),
    )
    with pytest.raises(ClaimControlError, match="cyclic"):
        validate_work_map(mapping)
