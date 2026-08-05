from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..serialization import load_document
from ..ux.catalog import LoadedUXCampaign, load_ux_campaign
from .models import UXMutation, UXMutationCatalog, UXMutationProofPlan


@dataclass(frozen=True)
class LoadedUXMutationProof:
    plan: UXMutationProofPlan
    plan_path: Path
    project_root: Path
    mutation_catalog: UXMutationCatalog
    mutation_catalog_path: Path
    ux_campaign: LoadedUXCampaign
    ux_campaign_path: Path
    selected_mutations: tuple[UXMutation, ...]


def _resolve_inside(root: Path, relative: str, field_name: str) -> Path:
    path = Path(relative)
    if path.is_absolute():
        raise ValueError(f"{field_name} must be relative")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"{field_name} escaped project_root")
    if not resolved.is_file():
        raise ValueError(f"{field_name} does not exist: {relative}")
    return resolved


def load_ux_mutation_proof(plan_file: str | Path) -> LoadedUXMutationProof:
    plan_path = Path(plan_file).resolve()
    plan = UXMutationProofPlan.model_validate(load_document(plan_path))
    project_root = (plan_path.parent / plan.project_root).resolve()
    if not project_root.is_dir():
        raise ValueError(f"project_root does not exist: {project_root}")

    mutation_catalog_path = _resolve_inside(
        project_root,
        plan.mutation_catalog_path,
        "mutation_catalog_path",
    )
    ux_campaign_path = _resolve_inside(
        project_root,
        plan.ux_campaign_path,
        "ux_campaign_path",
    )
    mutation_catalog = UXMutationCatalog.model_validate(
        load_document(mutation_catalog_path)
    )
    ux_campaign = load_ux_campaign(ux_campaign_path)

    if mutation_catalog.spec_ref != plan.spec_ref:
        raise ValueError("mutation proof plan and catalog must reference one UX1 SPEC")
    if mutation_catalog.target.revision != ux_campaign.plan.pins.target_revision:
        raise ValueError("mutation target revision differs from UX0 campaign target pin")
    if mutation_catalog.target.target_id != ux_campaign.target_manifest.id:
        raise ValueError("mutation target id differs from UX0 target manifest")
    if mutation_catalog.target.repository != ux_campaign.target_manifest.repository:
        raise ValueError("mutation target repository differs from UX0 target manifest")

    mutation_map = {
        mutation.mutation_id: mutation for mutation in mutation_catalog.mutations
    }
    selected_ids = (
        tuple(mutation_map)
        if plan.mutation_ids == ("*",)
        else tuple(plan.mutation_ids)
    )
    unknown = set(selected_ids) - set(mutation_map)
    if unknown:
        raise ValueError(f"proof plan selects unknown mutations: {sorted(unknown)}")
    selected = tuple(mutation_map[mutation_id] for mutation_id in selected_ids)

    journey_refs = {journey.ref for journey in ux_campaign.catalog.journeys}
    for mutation in selected:
        unknown_journeys = set(mutation.affected_journey_refs) - journey_refs
        if unknown_journeys:
            raise ValueError(
                f"mutation {mutation.mutation_id} references unknown journeys: "
                f"{sorted(unknown_journeys)}"
            )

    return LoadedUXMutationProof(
        plan=plan,
        plan_path=plan_path,
        project_root=project_root,
        mutation_catalog=mutation_catalog,
        mutation_catalog_path=mutation_catalog_path,
        ux_campaign=ux_campaign,
        ux_campaign_path=ux_campaign_path,
        selected_mutations=selected,
    )
