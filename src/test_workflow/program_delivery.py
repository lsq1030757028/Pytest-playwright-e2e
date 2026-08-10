from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ProgramDeliveryError(ValueError):
    """Raised when Program Delivery state is internally inconsistent."""


@dataclass(frozen=True)
class SelectionDecision:
    selected_work_item_id: str | None
    candidates: tuple[str, ...]
    excluded: tuple[tuple[str, str], ...]


def load_program_delivery(path: Path | str) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ProgramDeliveryError("Program Delivery SSOT must be a mapping")
    validate_program_delivery(payload)
    return payload


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProgramDeliveryError(f"{label} must be a mapping")
    return value


def _work_items_by_id(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_items = data.get("work_items")
    if not isinstance(raw_items, list):
        raise ProgramDeliveryError("work_items must be a list")
    items: dict[str, dict[str, Any]] = {}
    for raw_item in raw_items:
        item = _require_mapping(raw_item, "work item")
        work_item_id = item.get("work_item_id")
        if not isinstance(work_item_id, str) or not work_item_id:
            raise ProgramDeliveryError("every work item requires work_item_id")
        if work_item_id in items:
            raise ProgramDeliveryError(f"duplicate work_item_id: {work_item_id}")
        items[work_item_id] = item
    return items


def _validate_slice_graph(slices: dict[str, Any]) -> None:
    incoming = {slice_id: 0 for slice_id in slices}
    outgoing: dict[str, list[str]] = {slice_id: [] for slice_id in slices}
    for slice_id, raw_slice in slices.items():
        slice_data = _require_mapping(raw_slice, f"product slice {slice_id}")
        dependencies = slice_data.get("dependencies", [])
        if not isinstance(dependencies, list):
            raise ProgramDeliveryError(f"{slice_id} dependencies must be a list")
        for dependency in dependencies:
            if dependency not in slices:
                raise ProgramDeliveryError(
                    f"{slice_id} references unknown slice dependency {dependency}"
                )
            incoming[slice_id] += 1
            outgoing[dependency].append(slice_id)

    queue = sorted(slice_id for slice_id, count in incoming.items() if count == 0)
    visited = 0
    while queue:
        slice_id = queue.pop(0)
        visited += 1
        for child in sorted(outgoing[slice_id]):
            incoming[child] -= 1
            if incoming[child] == 0:
                queue.append(child)
                queue.sort()
    if visited != len(slices):
        raise ProgramDeliveryError("product slice dependency graph contains a cycle")


def _validate_work_item_graph(items: dict[str, dict[str, Any]]) -> None:
    incoming = {work_item_id: 0 for work_item_id in items}
    outgoing: dict[str, list[str]] = {work_item_id: [] for work_item_id in items}
    for work_item_id, item in items.items():
        dependencies = item.get("dependencies", [])
        if not isinstance(dependencies, list):
            raise ProgramDeliveryError(f"{work_item_id} dependencies must be a list")
        for dependency in dependencies:
            if dependency not in items:
                raise ProgramDeliveryError(
                    f"{work_item_id} references unknown work dependency {dependency}"
                )
            incoming[work_item_id] += 1
            outgoing[dependency].append(work_item_id)

    queue = sorted(item_id for item_id, count in incoming.items() if count == 0)
    visited = 0
    while queue:
        work_item_id = queue.pop(0)
        visited += 1
        for child in sorted(outgoing[work_item_id]):
            incoming[child] -= 1
            if incoming[child] == 0:
                queue.append(child)
                queue.sort()
    if visited != len(items):
        raise ProgramDeliveryError("Work Item dependency graph contains a cycle")


def validate_program_delivery(data: dict[str, Any]) -> None:
    header = _require_mapping(data.get("program_delivery"), "program_delivery")
    if header.get("source_role") != "AUTHORITATIVE_DELIVERY":
        raise ProgramDeliveryError("canonical Program Delivery source role is invalid")
    if header.get("delivery_selection_authoritative") is not True:
        raise ProgramDeliveryError("canonical Program Delivery source must own selection")

    program = _require_mapping(data.get("program"), "program")
    if program.get("id") != "TEST_AGENT_RUNTIME_BETA":
        raise ProgramDeliveryError("unexpected top-level product")

    slices = _require_mapping(data.get("product_slices"), "product_slices")
    if set(slices) != {"BETA-A", "BETA-B", "BETA-C", "BETA-D", "BETA-E"}:
        raise ProgramDeliveryError("Program Delivery must define exactly BETA-A through BETA-E")
    _validate_slice_graph(slices)

    pointer = _require_mapping(data.get("execution_pointer"), "execution_pointer")
    active_slice = pointer.get("active_slice")
    if active_slice not in slices:
        raise ProgramDeliveryError(f"active_slice is unknown: {active_slice}")
    next_slice = pointer.get("next_slice_after_active")
    if next_slice is not None and next_slice not in slices:
        raise ProgramDeliveryError(f"next_slice_after_active is unknown: {next_slice}")

    policy = _require_mapping(data.get("selection_policy"), "selection_policy")
    class_order = policy.get("classes_in_order")
    if not isinstance(class_order, list) or len(class_order) != len(set(class_order)):
        raise ProgramDeliveryError("selection classes must be a unique ordered list")
    if not class_order or class_order[0] != "SECURITY_CORRECTNESS_REPAIR":
        raise ProgramDeliveryError("security/correctness repair must be first")
    if class_order[-1] != "UNMAPPED_HORIZONTAL_INFRASTRUCTURE":
        raise ProgramDeliveryError("unmapped horizontal infrastructure must be last")
    forbidden_signals = set(policy.get("forbidden_priority_signals", []))
    if {"milestone_number", "claim_registry_sequence"} - forbidden_signals:
        raise ProgramDeliveryError("forbidden priority signals are incomplete")

    items = _work_items_by_id(data)
    _validate_work_item_graph(items)
    dependency_closed_states = set(policy.get("dependency_closed_states", []))
    claimable_states = set(policy.get("claimable_states", []))
    critical_mapping_keys = tuple(policy.get("critical_path_requires_any", []))
    if not critical_mapping_keys:
        raise ProgramDeliveryError("critical path mapping rule is missing")

    for work_item_id, item in items.items():
        selection_class = item.get("selection_class")
        if selection_class not in class_order:
            raise ProgramDeliveryError(
                f"{work_item_id} has unknown selection class {selection_class}"
            )
        supports_slices = item.get("supports_slices", [])
        if not isinstance(supports_slices, list):
            raise ProgramDeliveryError(f"{work_item_id} supports_slices must be a list")
        for slice_id in supports_slices:
            if slice_id not in slices:
                raise ProgramDeliveryError(
                    f"{work_item_id} supports unknown product slice {slice_id}"
                )
        for key in critical_mapping_keys:
            mapped_slice = item.get(key)
            if mapped_slice is not None and mapped_slice not in slices:
                raise ProgramDeliveryError(
                    f"{work_item_id} {key} references unknown slice {mapped_slice}"
                )

        if item.get("state") in claimable_states:
            if not item.get("authority_issue") or not item.get("required_spec"):
                raise ProgramDeliveryError(
                    f"READY work item lacks authority/spec: {work_item_id}"
                )
            for dependency in item.get("dependencies", []):
                dependency_state = items[dependency].get("state")
                if dependency_state not in dependency_closed_states:
                    raise ProgramDeliveryError(
                        f"READY work item has open dependency: {work_item_id} -> {dependency}"
                    )

    critical_path = pointer.get("critical_path")
    if not isinstance(critical_path, list) or not critical_path:
        raise ProgramDeliveryError("critical_path must be a non-empty list")
    for work_item_id in critical_path:
        if work_item_id not in items:
            raise ProgramDeliveryError(f"critical path references unknown item {work_item_id}")
        item = items[work_item_id]
        if not any(item.get(key) for key in critical_mapping_keys):
            raise ProgramDeliveryError(
                f"critical path item lacks product mapping: {work_item_id}"
            )

    source_roles = _require_mapping(data.get("source_roles"), "source_roles")
    machine_authorities = [
        path
        for path, raw_role in source_roles.items()
        if isinstance(raw_role, dict) and raw_role.get("role") == "AUTHORITATIVE_DELIVERY"
    ]
    if machine_authorities != ["docs/program-delivery-ssot.yaml"]:
        raise ProgramDeliveryError(
            "exactly docs/program-delivery-ssot.yaml must be AUTHORITATIVE_DELIVERY"
        )
    for path, raw_role in source_roles.items():
        role = _require_mapping(raw_role, f"source role {path}")
        if path != "docs/program-delivery-ssot.yaml" and role.get("may_select_next_work"):
            raise ProgramDeliveryError(f"non-authoritative source may select work: {path}")

    claims_role = source_roles.get(
        "ops/hourly-github-relay-control:.agent/relay/work-claims.json"
    )
    claims_role = _require_mapping(claims_role, "claim registry source role")
    if claims_role.get("role") != "OPERATIONAL_EXECUTION_STATE_ONLY":
        raise ProgramDeliveryError("claim registry must remain operational-only")


def select_next_work_item(
    data: dict[str, Any],
    *,
    unavailable_work_item_ids: Iterable[str] = (),
) -> SelectionDecision:
    """Select delivery priority; claims only remove unavailable ownership candidates."""

    validate_program_delivery(data)
    items = _work_items_by_id(data)
    policy = data["selection_policy"]
    class_rank = {
        class_name: index for index, class_name in enumerate(policy["classes_in_order"])
    }
    claimable_states = set(policy["claimable_states"])
    dependency_closed_states = set(policy["dependency_closed_states"])
    unavailable = set(unavailable_work_item_ids)

    candidates: list[dict[str, Any]] = []
    excluded: list[tuple[str, str]] = []
    for work_item_id, item in items.items():
        if item.get("state") not in claimable_states:
            excluded.append((work_item_id, f"state:{item.get('state')}"))
            continue
        if work_item_id in unavailable:
            excluded.append((work_item_id, "execution_ownership_unavailable"))
            continue
        open_dependencies = [
            dependency
            for dependency in item.get("dependencies", [])
            if items[dependency].get("state") not in dependency_closed_states
        ]
        if open_dependencies:
            excluded.append(
                (work_item_id, "dependencies:" + ",".join(sorted(open_dependencies)))
            )
            continue
        candidates.append(item)

    candidates.sort(
        key=lambda item: (
            class_rank[item["selection_class"]],
            -int(item.get("priority", 0)),
            item["work_item_id"],
        )
    )
    selected = candidates[0]["work_item_id"] if candidates else None
    return SelectionDecision(
        selected_work_item_id=selected,
        candidates=tuple(item["work_item_id"] for item in candidates),
        excluded=tuple(sorted(excluded)),
    )
