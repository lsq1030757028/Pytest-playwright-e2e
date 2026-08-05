from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..serialization import load_document
from ..targets import TargetManifest
from .models import UXCampaignPlan, UXCatalog

_ENV_PATTERN = re.compile(r"^\$\{([A-Z][A-Z0-9_]*)\}$")


@dataclass(frozen=True)
class LoadedUXCampaign:
    plan: UXCampaignPlan
    plan_path: Path
    catalog: UXCatalog
    catalog_path: Path
    target_manifest: TargetManifest
    target_manifest_path: Path


def _expand_environment(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _expand_environment(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_environment(item) for item in value]
    if isinstance(value, str):
        match = _ENV_PATTERN.fullmatch(value)
        if match:
            variable = match.group(1)
            try:
                return os.environ[variable]
            except KeyError as exc:
                raise ValueError(
                    f"required UX campaign environment variable is unset: {variable}"
                ) from exc
    return value


def _resolve_inside(root: Path, relative: str, field_name: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field_name} must be a relative path without traversal")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"{field_name} escaped the UX campaign directory")
    if not resolved.is_file():
        raise ValueError(f"{field_name} does not exist: {relative}")
    return resolved


def load_ux_campaign(plan_file: str | Path) -> LoadedUXCampaign:
    plan_path = Path(plan_file).resolve()
    payload = _expand_environment(load_document(plan_path))
    plan = UXCampaignPlan.model_validate(payload)
    root = plan_path.parent
    catalog_path = _resolve_inside(root, plan.catalog_path, "catalog_path")
    target_path = _resolve_inside(root, plan.target_manifest_path, "target_manifest_path")
    catalog = UXCatalog.model_validate(_expand_environment(load_document(catalog_path)))
    target_manifest = TargetManifest.model_validate(load_document(target_path))

    if catalog.spec_ref != plan.spec_ref:
        raise ValueError("UX plan and catalog must reference the same SPEC")
    if target_manifest.revision != plan.pins.target_revision:
        raise ValueError("UX target revision does not match the campaign pin")

    journey_ids = {journey.journey_id for journey in catalog.journeys}
    selected = journey_ids if plan.journey_ids == ("*",) else set(plan.journey_ids)
    unknown = selected - journey_ids
    if unknown:
        raise ValueError(f"UX plan selects unknown journeys: {sorted(unknown)}")

    return LoadedUXCampaign(
        plan=plan,
        plan_path=plan_path,
        catalog=catalog,
        catalog_path=catalog_path,
        target_manifest=target_manifest,
        target_manifest_path=target_path,
    )
