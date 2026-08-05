from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ..integrity import sha256_file
from ..serialization import dump_model, load_model
from ..targets import TargetManager
from .catalog import LoadedUXCampaign, load_ux_campaign
from .evaluator import (
    RuleBasedUXCritic,
    build_actor_input,
    canonical_digest,
    environment_digest,
    evaluate_journey,
)
from .execution import TodoMVCJourneyExecutor, metrics_for
from .models import (
    ActorJourneyInput,
    EvidenceLevel,
    ExperienceEnvironment,
    InteractionKind,
    SyntheticUserProfile,
    UXArtifactManifest,
    UXCampaignPlan,
    UXCampaignReport,
    UXCatalog,
    UXEvaluation,
    UXJourney,
    UXJourneyRun,
    UXReplayManifest,
    UXVerdict,
)
from .semantic_state import safe_normalized_todo_state, semantic_snapshot


class UXShadowRunner:
    def validate(self, plan_file: str | Path) -> LoadedUXCampaign:
        return load_ux_campaign(plan_file)

    def run(
        self,
        plan_file: str | Path,
        *,
        workspace: str | Path,
        output_dir: str | Path,
    ) -> UXCampaignReport:
        loaded = load_ux_campaign(plan_file)
        return self.run_loaded(loaded, workspace=workspace, output_dir=output_dir)

    def run_loaded(
        self,
        loaded: LoadedUXCampaign,
        *,
        workspace: str | Path,
        output_dir: str | Path,
    ) -> UXCampaignReport:
        root = Path(output_dir).resolve()
        if root.exists() and any(root.iterdir()):
            raise ValueError(f"UX output directory must be empty: {root}")
        root.mkdir(parents=True, exist_ok=True)
        input_dir = root / "input"
        evidence_dir = root / "evidence"
        input_dir.mkdir()
        evidence_dir.mkdir()

        normalized_plan = loaded.plan.model_copy(
            update={
                "catalog_path": "catalog.yaml",
                "target_manifest_path": "target-manifest.yaml",
            }
        )
        dump_model(input_dir / "campaign.json", normalized_plan)
        dump_model(input_dir / "catalog.yaml", loaded.catalog)
        dump_model(input_dir / "target-manifest.yaml", loaded.target_manifest)

        workspace_root = Path(workspace).resolve()
        workspace_root.mkdir(parents=True, exist_ok=True)
        target_manager = TargetManager()
        target = target_manager.materialize(
            loaded.target_manifest_path,
            workspace_root / "target",
            install=True,
        )
        selected_ids = self._selected_ids(loaded.plan, loaded.catalog)
        journeys = {item.journey_id: item for item in loaded.catalog.journeys}
        profiles = {item.ref: item for item in loaded.catalog.profiles}
        environments = {item.ref: item for item in loaded.catalog.environments}
        runs: list[UXJourneyRun] = []

        with target_manager.process(target, log_dir=root / "target-logs") as running:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    for journey_id in selected_ids:
                        journey = journeys[journey_id]
                        runs.append(
                            self._execute_journey(
                                browser=browser,
                                base_url=running.base_url,
                                journey=journey,
                                profile=profiles[journey.persona_refs[0]],
                                environment=environments[journey.environment_refs[0]],
                                target_revision=target.revision,
                                evidence_root=evidence_dir,
                            )
                        )
                finally:
                    browser.close()

        report = self._build_report(loaded.plan, tuple(runs))
        dump_model(root / "report.json", report)
        (root / "report.md").write_text(self.render_markdown(report), encoding="utf-8")
        self._write_manifests(root, report)
        return report

    def replay(
        self,
        bundle_dir: str | Path,
        *,
        workspace: str | Path,
    ) -> UXCampaignReport:
        root = Path(bundle_dir).resolve()
        artifact_manifest = load_model(root / "artifact-manifest.json", UXArtifactManifest)
        replay_manifest = load_model(root / "replay-manifest.json", UXReplayManifest)
        if canonical_digest(artifact_manifest.files) != artifact_manifest.manifest_digest:
            raise ValueError("UX artifact manifest digest mismatch")
        if artifact_manifest.manifest_digest != replay_manifest.artifact_manifest_digest:
            raise ValueError("UX replay and artifact manifest digests differ")
        for relative, expected_hash in artifact_manifest.files.items():
            path = root / relative
            if not path.is_file():
                raise ValueError(f"UX replay artifact is missing: {relative}")
            observed = sha256_file(path)
            if observed != expected_hash:
                raise ValueError(
                    f"UX replay artifact hash mismatch for {relative}: "
                    f"expected={expected_hash}, observed={observed}"
                )
        for relative, expected_hash in replay_manifest.input_files.items():
            if sha256_file(root / relative) != expected_hash:
                raise ValueError(f"UX replay input changed: {relative}")

        workspace_root = Path(workspace).resolve()
        if workspace_root.exists():
            shutil.rmtree(workspace_root)
        with tempfile.TemporaryDirectory(prefix="ux-shadow-replay-") as temp:
            replayed = self.run(
                root / "input" / "campaign.json",
                workspace=workspace_root,
                output_dir=Path(temp) / "output",
            )
        if replayed.semantic_digest != replay_manifest.semantic_digest:
            raise ValueError(
                "independent UX replay drifted: "
                f"expected={replay_manifest.semantic_digest}, "
                f"observed={replayed.semantic_digest}"
            )
        return replayed

    @staticmethod
    def _selected_ids(plan: UXCampaignPlan, catalog: UXCatalog) -> tuple[str, ...]:
        available = {item.journey_id for item in catalog.journeys}
        selected = (
            tuple(item.journey_id for item in catalog.journeys)
            if plan.journey_ids == ("*",)
            else tuple(plan.journey_ids)
        )
        unknown = set(selected) - available
        if unknown:
            raise ValueError(f"unknown UX journeys: {sorted(unknown)}")
        return selected

    def _execute_journey(
        self,
        *,
        browser: Any,
        base_url: str,
        journey: UXJourney,
        profile: SyntheticUserProfile,
        environment: ExperienceEnvironment,
        target_revision: str,
        evidence_root: Path,
    ) -> UXJourneyRun:
        actor_input: ActorJourneyInput = build_actor_input(journey, profile, environment)
        journey_dir = evidence_root / journey.journey_id
        journey_dir.mkdir(parents=True, exist_ok=True)
        trace_relative = Path("evidence") / journey.journey_id / "trace.zip"
        screenshot_relative = Path("evidence") / journey.journey_id / "final.png"
        semantic_relative = Path("evidence") / journey.journey_id / "semantic.json"
        trace_path = journey_dir / "trace.zip"
        screenshot_path = journey_dir / "final.png"
        semantic_path = journey_dir / "semantic.json"

        context = browser.new_context(
            viewport={
                "width": environment.device_profile.viewport_width,
                "height": environment.device_profile.viewport_height,
            },
            device_scale_factor=environment.device_profile.device_scale_factor,
            locale=environment.locale_timezone.locale,
            timezone_id=environment.locale_timezone.timezone,
            reduced_motion=(
                "reduce"
                if environment.device_profile.prefers_reduced_motion
                else "no-preference"
            ),
        )
        context.tracing.start(screenshots=True, snapshots=True, sources=False)
        page = context.new_page()
        executor = TodoMVCJourneyExecutor(page, trace_relative)
        checkpoint_results: dict[str, bool] = {}
        runtime_error: str | None = None
        observations: dict[str, Any] = {}
        try:
            page.goto(base_url, wait_until="domcontentloaded")
            executor.prepare()
            observations = executor.run(journey)
            checkpoint_results = {
                checkpoint: bool(observations.get(checkpoint, False))
                for checkpoint in journey.oracle.required_checkpoints
            }
        except Exception as exc:
            runtime_error = f"{type(exc).__name__}: {exc}"
            state = safe_normalized_todo_state(page, executor.adapter)
            executor.append_event(
                kind=InteractionKind.ACTION_FAILED,
                target=f"journey:{journey.journey_id}",
                before=state,
                after=state,
                result=runtime_error,
            )
        finally:
            semantic_path.write_text(
                json.dumps(semantic_snapshot(page), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            page.screenshot(path=str(screenshot_path), full_page=True)
            context.tracing.stop(path=str(trace_path))
            context.close()

        events = tuple(executor.events)
        metrics = metrics_for(journey, checkpoint_results, observations, events)
        evaluation = (
            UXEvaluation(
                verdict=UXVerdict.INVALID,
                evidence_level=EvidenceLevel.E3,
                failures=(f"runtime_boundary_error:{runtime_error}",),
                blocker=False,
            )
            if runtime_error is not None
            else evaluate_journey(journey, checkpoint_results, metrics)
        )
        evidence_refs = (
            trace_relative.as_posix(),
            screenshot_relative.as_posix(),
            semantic_relative.as_posix(),
        )
        findings = RuleBasedUXCritic().propose(
            journey=journey,
            metrics=metrics,
            event_refs=tuple(item.event_id for item in events),
            evidence_refs=evidence_refs,
        )
        return UXJourneyRun(
            run_id=f"ux0-todomvc-shadow:{journey.journey_id}:1",
            journey_ref=journey.ref,
            profile_ref=profile.ref,
            environment_ref=environment.ref,
            environment_hash=environment_digest(environment),
            actor_input_hash=canonical_digest(actor_input.model_dump(mode="json")),
            target_revision=target_revision,
            events=events,
            checkpoint_results=checkpoint_results,
            metrics=metrics,
            findings=findings,
            evaluation=evaluation,
            evidence_path=(Path("evidence") / journey.journey_id).as_posix(),
        )

    @staticmethod
    def _build_report(
        plan: UXCampaignPlan,
        runs: tuple[UXJourneyRun, ...],
    ) -> UXCampaignReport:
        verdict = UXShadowRunner._campaign_verdict(runs)
        payload = {
            "schema_version": "1.0",
            "campaign_id": plan.campaign_id,
            "spec_ref": plan.spec_ref,
            "approval_ref": plan.approval_ref,
            "mandate_ref": plan.mandate_ref,
            "mode": plan.mode.value,
            "pins": plan.pins.model_dump(mode="json"),
            "runs": [run.model_dump(mode="json") for run in runs],
            "verdict": verdict.value,
            "release_effect": "NONBLOCKING_SHADOW",
            "human_uat_required": True,
        }
        return UXCampaignReport(**payload, semantic_digest=canonical_digest(payload))

    @staticmethod
    def _campaign_verdict(runs: Sequence[UXJourneyRun]) -> UXVerdict:
        verdicts = {run.evaluation.verdict for run in runs}
        for verdict in (
            UXVerdict.INVALID,
            UXVerdict.BLOCKED,
            UXVerdict.FAIL,
            UXVerdict.INCONCLUSIVE,
            UXVerdict.WARN,
        ):
            if verdict in verdicts:
                return verdict
        return UXVerdict.PASS

    @staticmethod
    def render_markdown(report: UXCampaignReport) -> str:
        lines = [
            f"# Synthetic User Shadow Report: {report.campaign_id}",
            "",
            f"- Verdict: `{report.verdict.value}`",
            f"- Runtime mode: `{report.mode.value}`",
            f"- Release effect: `{report.release_effect}`",
            f"- Human UAT required: `{report.human_uat_required}`",
            f"- Journeys: `{len(report.runs)}`",
            f"- Semantic digest: `{report.semantic_digest}`",
            "",
            "| Journey | Verdict | Checkpoints | Steps | Findings |",
            "|---|---|---:|---:|---:|",
        ]
        for run in report.runs:
            lines.append(
                f"| {run.journey_ref} | {run.evaluation.verdict.value} | "
                f"{run.metrics.checkpoint_completed}/{run.metrics.checkpoint_total} | "
                f"{run.metrics.step_count} | {len(run.findings)} |"
            )
        lines.extend(
            [
                "",
                "## UAT handoff",
                "",
                "Synthetic User evidence is pre-UAT support. Human UAT remains required.",
            ]
        )
        return "\n".join(lines) + "\n"

    @staticmethod
    def _write_manifests(root: Path, report: UXCampaignReport) -> None:
        excluded = {"artifact-manifest.json", "replay-manifest.json"}
        files = {
            path.relative_to(root).as_posix(): sha256_file(path)
            for path in sorted(item for item in root.rglob("*") if item.is_file())
            if path.name not in excluded
        }
        manifest_digest = canonical_digest(files)
        dump_model(
            root / "artifact-manifest.json",
            UXArtifactManifest(
                campaign_id=report.campaign_id,
                files=files,
                manifest_digest=manifest_digest,
            ),
        )
        input_files = {
            relative: digest
            for relative, digest in files.items()
            if relative.startswith("input/")
        }
        dump_model(
            root / "replay-manifest.json",
            UXReplayManifest(
                campaign_id=report.campaign_id,
                spec_ref=report.spec_ref,
                approval_ref=report.approval_ref,
                semantic_digest=report.semantic_digest,
                artifact_manifest_digest=manifest_digest,
                input_files=input_files,
            ),
        )
