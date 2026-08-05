from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..serialization import load_document
from .models import FixtureCatalog, MemoryBenchmarkPlan, ScenarioCatalog

_ENV_PATTERN = re.compile(r"^\$\{([A-Z][A-Z0-9_]*)\}$")


@dataclass(frozen=True)
class LoadedBenchmark:
    plan: MemoryBenchmarkPlan
    plan_path: Path
    catalog: ScenarioCatalog
    catalog_path: Path
    fixtures: FixtureCatalog
    fixture_catalog_path: Path


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
                message = f"required benchmark environment variable is unset: {variable}"
                raise ValueError(message) from exc
    return value


def _resolve_inside(root: Path, relative: str, field_name: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field_name} must be a relative path without traversal")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"{field_name} escaped the benchmark plan directory")
    if not resolved.is_file():
        raise ValueError(f"{field_name} does not exist: {relative}")
    return resolved


def load_benchmark(plan_file: str | Path) -> LoadedBenchmark:
    plan_path = Path(plan_file).resolve()
    payload = _expand_environment(load_document(plan_path))
    plan = MemoryBenchmarkPlan.model_validate(payload)
    root = plan_path.parent
    catalog_path = _resolve_inside(root, plan.catalog_path, "catalog_path")
    fixture_path = _resolve_inside(root, plan.fixture_catalog_path, "fixture_catalog_path")
    catalog = ScenarioCatalog.model_validate(load_document(catalog_path))
    fixtures = FixtureCatalog.model_validate(load_document(fixture_path))

    if catalog.spec_ref != plan.spec_ref or fixtures.spec_ref != plan.spec_ref:
        raise ValueError("plan, scenario catalog, and fixture catalog must reference one SPEC")

    scenario_ids = {scenario.id for scenario in catalog.scenarios}
    fixture_ids = {fixture.scenario_id for fixture in fixtures.fixtures}
    if scenario_ids != fixture_ids:
        missing_fixtures = sorted(scenario_ids - fixture_ids)
        unknown_fixtures = sorted(fixture_ids - scenario_ids)
        raise ValueError(
            "scenario and fixture catalogs differ: "
            f"missing={missing_fixtures}, unknown={unknown_fixtures}"
        )

    selected = scenario_ids if plan.scenario_ids == ("*",) else set(plan.scenario_ids)
    unknown_selected = selected - scenario_ids
    if unknown_selected:
        raise ValueError(f"plan selects unknown scenarios: {sorted(unknown_selected)}")

    return LoadedBenchmark(
        plan=plan,
        plan_path=plan_path,
        catalog=catalog,
        catalog_path=catalog_path,
        fixtures=fixtures,
        fixture_catalog_path=fixture_path,
    )
