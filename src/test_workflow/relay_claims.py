from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from test_workflow.program_delivery import (
    ProgramDeliveryError,
    select_next_work_item,
    validate_program_delivery,
)

ACTIVE_CLAIM_STATES = frozenset(
    {"CLAIMED", "IN_PROGRESS", "EVIDENCE_READY", "INTEGRATION_WAITING", "INTEGRATING"}
)


class ClaimControlError(ValueError):
    """Base error for deterministic claim-control failures."""


class AllocatorDisabled(ClaimControlError):
    """Raised when the operational registry is intentionally disabled."""


class RegistryRevisionConflict(ClaimControlError):
    """Raised when the caller did not use the registry revision it read."""


class NoClaimableWork(ClaimControlError):
    """Raised when every Work Item is blocked or conflicts with an active claim."""

    def __init__(self, rejected: Mapping[str, str]) -> None:
        self.rejected = dict(rejected)
        super().__init__("no claimable Work Item")


class ClaimFenceViolation(ClaimControlError):
    """Raised before a mutation when ownership or branch fencing no longer matches."""


@dataclass(frozen=True)
class SelectionResult:
    work_item_id: str | None
    rejected: dict[str, str]


@dataclass(frozen=True)
class AllocationResult:
    registry: dict[str, Any]
    claim: dict[str, Any]
    rejected: dict[str, str]


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ClaimControlError("timestamp must include a timezone")
    return parsed.astimezone(UTC)


def format_utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise ClaimControlError("timestamp must include a timezone")
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _items_by_id(work_map: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    items = work_map.get("work_items")
    if not isinstance(items, list) or not items:
        raise ClaimControlError("work_items must be a non-empty list")
    indexed: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            raise ClaimControlError("each Work Item must be an object")
        work_item_id = item.get("work_item_id")
        if not isinstance(work_item_id, str) or not work_item_id:
            raise ClaimControlError("each Work Item needs a stable work_item_id")
        if work_item_id in indexed:
            raise ClaimControlError(f"duplicate Work Item: {work_item_id}")
        indexed[work_item_id] = item
    return indexed


def _validate_legacy_work_map(work_map: Mapping[str, Any]) -> None:
    indexed = _items_by_id(work_map)
    groups = work_map.get("integration_groups")
    if not isinstance(groups, dict) or not groups:
        raise ClaimControlError("integration_groups must be declared")

    required = {
        "work_item_id",
        "state",
        "priority",
        "dependencies",
        "authority_issue",
        "required_spec",
        "target_branch",
        "target_pr",
        "exclusive_domain",
        "integration_group",
    }
    for work_item_id, item in indexed.items():
        missing = required - item.keys()
        if missing:
            raise ClaimControlError(f"{work_item_id} missing fields: {sorted(missing)}")
        if not isinstance(item["exclusive_domain"], str) or not item["exclusive_domain"]:
            raise ClaimControlError(f"{work_item_id} needs one exclusive_domain")
        if item["integration_group"] not in groups:
            raise ClaimControlError(
                f"{work_item_id} references an unknown integration group"
            )
        dependencies = item["dependencies"]
        if not isinstance(dependencies, list):
            raise ClaimControlError(f"{work_item_id} dependencies must be a list")
        for dependency in dependencies:
            if dependency not in indexed:
                raise ClaimControlError(
                    f"{work_item_id} has unknown dependency {dependency}"
                )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(work_item_id: str) -> None:
        if work_item_id in visiting:
            raise ClaimControlError(f"cyclic Work Item dependency at {work_item_id}")
        if work_item_id in visited:
            return
        visiting.add(work_item_id)
        for dependency in indexed[work_item_id]["dependencies"]:
            visit(dependency)
        visiting.remove(work_item_id)
        visited.add(work_item_id)

    for work_item_id in sorted(indexed):
        visit(work_item_id)


def validate_work_map(work_map: Mapping[str, Any]) -> None:
    if "program_delivery" in work_map:
        try:
            validate_program_delivery(dict(work_map))
        except ProgramDeliveryError as error:
            raise ClaimControlError(str(error)) from error
        return
    _validate_legacy_work_map(work_map)


def validate_registry(registry: Mapping[str, Any]) -> None:
    if registry.get("schema_version") != 1:
        raise ClaimControlError("unsupported claim registry schema")
    if not isinstance(registry.get("revision"), int) or registry["revision"] < 0:
        raise ClaimControlError("registry revision must be a non-negative integer")
    if (
        not isinstance(registry.get("claim_sequence"), int)
        or registry["claim_sequence"] < 0
    ):
        raise ClaimControlError("claim_sequence must be a non-negative integer")
    if not isinstance(registry.get("claims"), dict):
        raise ClaimControlError("claims must be an object")
    if not isinstance(registry.get("integration_queue"), list):
        raise ClaimControlError("integration_queue must be a list")
    if not isinstance(registry.get("recovered_claims"), list):
        raise ClaimControlError("recovered_claims must be a list")


def _require_revision(registry: Mapping[str, Any], expected_revision: int) -> None:
    if registry["revision"] != expected_revision:
        raise RegistryRevisionConflict(
            f"expected registry revision {expected_revision}, "
            f"found {registry['revision']}"
        )


def _blocking_claims(registry: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        claim
        for claim in registry["claims"].values()
        if claim.get("state") in ACTIVE_CLAIM_STATES
    ]


def _program_ownership_conflicts(
    program_delivery: Mapping[str, Any],
    registry: Mapping[str, Any],
) -> tuple[set[str], dict[str, str]]:
    indexed = _items_by_id(program_delivery)
    active = _blocking_claims(registry)
    active_domains = {claim.get("exclusive_domain") for claim in active}
    active_branches = {
        claim.get("target_branch") for claim in active if claim.get("target_branch")
    }
    active_prs = {
        claim.get("target_pr")
        for claim in active
        if claim.get("target_pr") is not None
    }
    claimed_items = {claim.get("work_item_id") for claim in active}
    incompatibilities = program_delivery.get("domain_incompatibilities", {})
    if not isinstance(incompatibilities, dict):
        raise ClaimControlError("domain_incompatibilities must be a mapping")

    unavailable: set[str] = set()
    reasons: dict[str, str] = {}
    for work_item_id, item in indexed.items():
        if work_item_id in claimed_items:
            unavailable.add(work_item_id)
            reasons[work_item_id] = "already_claimed"
            continue

        domain = item.get("exclusive_domain")
        if domain in active_domains:
            unavailable.add(work_item_id)
            reasons[work_item_id] = f"domain_conflict:{domain}"
            continue

        incompatible = set(incompatibilities.get(domain, []))
        reverse_incompatible = {
            other_domain
            for other_domain, blocked in incompatibilities.items()
            if isinstance(blocked, list) and domain in blocked
        }
        conflicting_domains = sorted(
            (incompatible | reverse_incompatible) & active_domains
        )
        if conflicting_domains:
            unavailable.add(work_item_id)
            reasons[work_item_id] = (
                f"incompatible_domain:{','.join(conflicting_domains)}"
            )
            continue

        target_branch = item.get("target_branch")
        if target_branch and target_branch in active_branches:
            unavailable.add(work_item_id)
            reasons[work_item_id] = f"branch_conflict:{target_branch}"
            continue

        target_pr = item.get("target_pr")
        if target_pr is not None and target_pr in active_prs:
            unavailable.add(work_item_id)
            reasons[work_item_id] = f"pr_conflict:{target_pr}"

    return unavailable, reasons


def _select_program_work_item(
    program_delivery: Mapping[str, Any],
    registry: Mapping[str, Any],
) -> SelectionResult:
    unavailable, ownership_reasons = _program_ownership_conflicts(
        program_delivery, registry
    )
    try:
        decision = select_next_work_item(
            dict(program_delivery),
            unavailable_work_item_ids=unavailable,
        )
    except ProgramDeliveryError as error:
        raise ClaimControlError(str(error)) from error

    rejected = dict(decision.excluded)
    for work_item_id, reason in tuple(rejected.items()):
        if reason == "execution_ownership_unavailable":
            rejected[work_item_id] = ownership_reasons[work_item_id]
    return SelectionResult(
        work_item_id=decision.selected_work_item_id,
        rejected=rejected,
    )


def _select_legacy_work_item(
    work_map: Mapping[str, Any],
    registry: Mapping[str, Any],
) -> SelectionResult:
    indexed = _items_by_id(work_map)
    active = _blocking_claims(registry)
    active_domains = {claim.get("exclusive_domain") for claim in active}
    active_branches = {
        claim.get("target_branch") for claim in active if claim.get("target_branch")
    }
    active_prs = {
        claim.get("target_pr")
        for claim in active
        if claim.get("target_pr") is not None
    }
    claimed_items = {claim.get("work_item_id") for claim in active}
    incompatibilities = work_map.get("domain_incompatibilities", {})
    closed_items = {
        item_id for item_id, item in indexed.items() if item.get("state") == "CLOSED"
    }

    rejected: dict[str, str] = {}
    ordered = sorted(
        indexed.values(),
        key=lambda item: (-int(item["priority"]), str(item["work_item_id"])),
    )
    for item in ordered:
        work_item_id = item["work_item_id"]
        if item["state"] != "READY":
            rejected[work_item_id] = f"state:{item['state']}"
            continue
        missing_dependencies = sorted(set(item["dependencies"]) - closed_items)
        if missing_dependencies:
            rejected[work_item_id] = f"dependencies:{','.join(missing_dependencies)}"
            continue
        if item["authority_issue"] is None or not item["required_spec"]:
            rejected[work_item_id] = "authority_or_spec_missing"
            continue
        if work_item_id in claimed_items:
            rejected[work_item_id] = "already_claimed"
            continue
        domain = item["exclusive_domain"]
        if domain in active_domains:
            rejected[work_item_id] = f"domain_conflict:{domain}"
            continue
        incompatible = set(incompatibilities.get(domain, []))
        reverse_incompatible = {
            other_domain
            for other_domain, blocked in incompatibilities.items()
            if domain in blocked
        }
        conflicting_domains = sorted(
            (incompatible | reverse_incompatible) & active_domains
        )
        if conflicting_domains:
            rejected[work_item_id] = (
                f"incompatible_domain:{','.join(conflicting_domains)}"
            )
            continue
        target_branch = item.get("target_branch")
        if target_branch and target_branch in active_branches:
            rejected[work_item_id] = f"branch_conflict:{target_branch}"
            continue
        target_pr = item.get("target_pr")
        if target_pr is not None and target_pr in active_prs:
            rejected[work_item_id] = f"pr_conflict:{target_pr}"
            continue
        return SelectionResult(work_item_id=work_item_id, rejected=rejected)
    return SelectionResult(work_item_id=None, rejected=rejected)


def select_work_item(
    work_map: Mapping[str, Any],
    registry: Mapping[str, Any],
) -> SelectionResult:
    validate_work_map(work_map)
    validate_registry(registry)
    if "program_delivery" in work_map:
        return _select_program_work_item(work_map, registry)
    return _select_legacy_work_item(work_map, registry)


def allocate_next(
    work_map: Mapping[str, Any],
    registry: Mapping[str, Any],
    *,
    expected_revision: int,
    surface: str,
    now: datetime,
    branch_heads: Mapping[str, str],
    branch_overrides: Mapping[str, str] | None = None,
    lease_minutes: int = 120,
) -> AllocationResult:
    validate_registry(registry)
    if not registry.get("enabled", False):
        raise AllocatorDisabled("claim allocation is disabled")
    _require_revision(registry, expected_revision)
    selection = select_work_item(work_map, registry)
    if selection.work_item_id is None:
        raise NoClaimableWork(selection.rejected)

    indexed = _items_by_id(work_map)
    item = indexed[selection.work_item_id]
    override = (branch_overrides or {}).get(selection.work_item_id)
    target_branch = override or item.get("target_branch")
    if not target_branch:
        raise ClaimControlError(f"{selection.work_item_id} has no target branch")
    expected_head_sha = branch_heads.get(target_branch)
    if not expected_head_sha:
        raise ClaimControlError(f"missing branch head for {target_branch}")
    if now.tzinfo is None:
        raise ClaimControlError("now must include a timezone")

    sequence = int(registry["claim_sequence"]) + 1
    started_at = format_utc(now)
    token_time = now.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    claim_token = f"claim-{selection.work_item_id.lower()}-{sequence}-{token_time}"
    claim = {
        "work_item_id": selection.work_item_id,
        "claim_token": claim_token,
        "surface": surface,
        "state": "CLAIMED",
        "exclusive_domain": item["exclusive_domain"],
        "target_branch": target_branch,
        "target_pr": item.get("target_pr"),
        "expected_head_sha": expected_head_sha,
        "started_at": started_at,
        "heartbeat_at": started_at,
        "expires_at": format_utc(now + timedelta(minutes=lease_minutes)),
        "last_checkpoint": "CLAIMED",
    }
    updated = deepcopy(dict(registry))
    updated["revision"] = int(registry["revision"]) + 1
    updated["claim_sequence"] = sequence
    updated["claims"][selection.work_item_id] = claim
    return AllocationResult(
        registry=updated,
        claim=claim,
        rejected=selection.rejected,
    )


def assert_claim_fence(
    registry: Mapping[str, Any],
    *,
    work_item_id: str,
    claim_token: str,
    exclusive_domain: str,
    target_branch: str,
    actual_head_sha: str,
    now: datetime,
) -> None:
    validate_registry(registry)
    claim = registry["claims"].get(work_item_id)
    if not isinstance(claim, dict):
        raise ClaimFenceViolation("claim is missing")
    checks = {
        "claim_token": claim_token,
        "exclusive_domain": exclusive_domain,
        "target_branch": target_branch,
        "expected_head_sha": actual_head_sha,
    }
    for field, expected in checks.items():
        if claim.get(field) != expected:
            raise ClaimFenceViolation(f"claim fence mismatch: {field}")
    if claim.get("state") not in ACTIVE_CLAIM_STATES:
        raise ClaimFenceViolation("claim is not active")
    if parse_utc(claim["expires_at"]) <= now.astimezone(UTC):
        raise ClaimFenceViolation("claim is expired")


def heartbeat_claim(
    registry: Mapping[str, Any],
    *,
    expected_revision: int,
    work_item_id: str,
    claim_token: str,
    now: datetime,
    checkpoint: str,
    lease_minutes: int = 120,
) -> dict[str, Any]:
    validate_registry(registry)
    _require_revision(registry, expected_revision)
    updated = deepcopy(dict(registry))
    claim = updated["claims"].get(work_item_id)
    if not isinstance(claim, dict) or claim.get("claim_token") != claim_token:
        raise ClaimFenceViolation("claim ownership changed")
    claim["heartbeat_at"] = format_utc(now)
    claim["expires_at"] = format_utc(now + timedelta(minutes=lease_minutes))
    claim["last_checkpoint"] = checkpoint
    claim["state"] = "IN_PROGRESS"
    updated["revision"] += 1
    return updated


def recover_stale_claims(
    registry: Mapping[str, Any],
    *,
    expected_revision: int,
    now: datetime,
    activity: Mapping[str, Mapping[str, bool]],
) -> tuple[dict[str, Any], list[str], list[str]]:
    validate_registry(registry)
    _require_revision(registry, expected_revision)
    updated = deepcopy(dict(registry))
    recovered: list[str] = []
    protected: list[str] = []
    for work_item_id, claim in list(updated["claims"].items()):
        if claim.get("state") not in ACTIVE_CLAIM_STATES:
            continue
        if parse_utc(claim["expires_at"]) > now.astimezone(UTC):
            continue
        signals = activity.get(work_item_id, {})
        if any(
            signals.get(name, False)
            for name in ("recent_branch_activity", "recent_pr_activity", "active_ci")
        ):
            protected.append(work_item_id)
            continue
        recovered_claim = deepcopy(claim)
        recovered_claim["state"] = "STALE_RECOVERED"
        recovered_claim["recovered_at"] = format_utc(now)
        updated["recovered_claims"].append(recovered_claim)
        del updated["claims"][work_item_id]
        recovered.append(work_item_id)
    if recovered:
        updated["revision"] += 1
    return updated, recovered, protected


def enqueue_integration(
    registry: Mapping[str, Any],
    *,
    expected_revision: int,
    work_item_id: str,
    claim_token: str,
    now: datetime,
    security_or_correctness_repair: bool = False,
    dependency_unblocking: bool = False,
) -> dict[str, Any]:
    validate_registry(registry)
    _require_revision(registry, expected_revision)
    updated = deepcopy(dict(registry))
    claim = updated["claims"].get(work_item_id)
    if not isinstance(claim, dict) or claim.get("claim_token") != claim_token:
        raise ClaimFenceViolation("claim ownership changed")
    if claim.get("state") != "EVIDENCE_READY":
        raise ClaimControlError("only EVIDENCE_READY work can enter integration")
    if any(
        entry.get("work_item_id") == work_item_id
        for entry in updated["integration_queue"]
    ):
        raise ClaimControlError("Work Item is already in the integration queue")
    updated["integration_queue"].append(
        {
            "work_item_id": work_item_id,
            "claim_token": claim_token,
            "enqueued_at": format_utc(now),
            "security_or_correctness_repair": security_or_correctness_repair,
            "dependency_unblocking": dependency_unblocking,
            "state": "INTEGRATION_WAITING",
        }
    )
    claim["state"] = "INTEGRATION_WAITING"
    claim["last_checkpoint"] = "INTEGRATION_WAITING"
    updated["revision"] += 1
    return updated


def select_integration_entry(
    registry: Mapping[str, Any],
) -> dict[str, Any] | None:
    validate_registry(registry)
    eligible = [
        entry
        for entry in registry["integration_queue"]
        if entry.get("state") == "INTEGRATION_WAITING"
    ]
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda entry: (
            not bool(entry.get("security_or_correctness_repair")),
            not bool(entry.get("dependency_unblocking")),
            parse_utc(entry["enqueued_at"]),
            str(entry["work_item_id"]),
        ),
    )


def acquire_integration_lease(
    lease: Mapping[str, Any],
    registry: Mapping[str, Any],
    *,
    expected_revision: int,
    now: datetime,
    lease_minutes: int = 60,
) -> dict[str, Any]:
    if lease.get("schema_version") != 1:
        raise ClaimControlError("unsupported integration lease schema")
    if lease.get("revision") != expected_revision:
        raise RegistryRevisionConflict("integration lease revision changed")
    if lease.get("status") != "IDLE":
        raise ClaimControlError("integration lease is busy")
    entry = select_integration_entry(registry)
    if entry is None:
        raise ClaimControlError("integration queue is empty")
    sequence = int(lease.get("sequence", 0)) + 1
    token_time = now.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    updated = deepcopy(dict(lease))
    updated.update(
        {
            "revision": int(lease["revision"]) + 1,
            "sequence": sequence,
            "status": "ACTIVE",
            "integration_token": f"integration-{sequence}-{token_time}",
            "work_item_id": entry["work_item_id"],
            "started_at": format_utc(now),
            "expires_at": format_utc(now + timedelta(minutes=lease_minutes)),
        }
    )
    return updated
