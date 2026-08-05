from __future__ import annotations

import shutil
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..integrity import sha256_file
from ..serialization import dump_model, load_model
from ..targets import MaterializedTarget, TargetManager
from ..ux.catalog import LoadedUXCampaign
from ..ux.evaluator import build_actor_input, canonical_digest
from ..ux.models import UXCampaignReport, UXVerdict
from ..ux.shadow_runner import UXShadowRunner
from .catalog import LoadedUXMutationProof, load_ux_mutation_proof
from .models import (
    MutationCampaignMetrics,
    MutationOutcome,
    MutationProofResult,
    PatchEvidence,
    PhaseEvidence,
    ProofCampaignVerdict,
    ProofPhase,
    ProofState,
    ProofTransitionEvent,
    UXMutation,
    UXMutationArtifactManifest,
    UXMutationCampaignReport,
    UXMutationReplayManifest,
)
from .sandbox import TargetMutationSandbox, changed_files

_FORBIDDEN_ACTOR_KEYS = {
    "mutation_id",
    "mutation_family",
    "mutation_patch",
    "changed_file",
    "expected_failed_checkpoint",
    "preferred_locator_sequence",
    "expected_phase_verdict",
    "evaluator_scoring_key",
}

_ALLOWED_TRANSITIONS: dict[ProofState, set[ProofState]] = {
    ProofState.PLANNED: {
        ProofState.BASELINE_RUNNING,
        ProofState.BLOCKED,
        ProofState.INVALID_EVIDENCE,
    },
    ProofState.BASELINE_RUNNING: {
        ProofState.BASELINE_PROVEN,
        ProofState.BASELINE_FAILED,
        ProofState.BLOCKED,
        ProofState.INVALID_EVIDENCE,
    },
    ProofState.BASELINE_PROVEN: {
        ProofState.MUTATION_APPLYING,
        ProofState.BLOCKED,
        ProofState.INVALID_EVIDENCE,
    },
    ProofState.MUTATION_APPLYING: {
        ProofState.MUTATION_VERIFIED,
        ProofState.MUTATION_APPLY_FAILED,
        ProofState.INVALID_EVIDENCE,
    },
    ProofState.MUTATION_VERIFIED: {
        ProofState.MUTATED_RUNNING,
        ProofState.RESTORING,
        ProofState.BLOCKED,
        ProofState.INVALID_EVIDENCE,
    },
    ProofState.MUTATED_RUNNING: {
        ProofState.MUTATION_KILLED,
        ProofState.RESTORING,
        ProofState.MUTATION_SURVIVED,
        ProofState.BLOCKED,
        ProofState.INVALID_EVIDENCE,
    },
    ProofState.MUTATION_KILLED: {
        ProofState.RESTORING,
        ProofState.INVALID_EVIDENCE,
    },
    ProofState.RESTORING: {
        ProofState.RESTORE_VERIFIED,
        ProofState.RESTORE_FAILED,
        ProofState.INVALID_EVIDENCE,
    },
    ProofState.RESTORE_VERIFIED: {
        ProofState.RESTORED_RUNNING,
        ProofState.MUTATION_SURVIVED,
        ProofState.INVALID_EVIDENCE,
    },
    ProofState.RESTORED_RUNNING: {
        ProofState.CLOSED_PASS,
        ProofState.RESTORE_FAILED,
        ProofState.REPLAY_DRIFTED,
        ProofState.INVALID_EVIDENCE,
    },
    ProofState.CLOSED_PASS: set(),
    ProofState.BASELINE_FAILED: set(),
    ProofState.MUTATION_APPLY_FAILED: set(),
    ProofState.MUTATION_SURVIVED: set(),
    ProofState.RESTORE_FAILED: set(),
    ProofState.REPLAY_DRIFTED: set(),
    ProofState.INVALID_EVIDENCE: set(),
    ProofState.BLOCKED: set(),
}


@dataclass
class _TransitionRecorder:
    mutation_id: str
    current: ProofState = ProofState.PLANNED

    def __post_init__(self) -> None:
        self.events: list[ProofTransitionEvent] = []

    def move(self, target: ProofState, reason: str) -> None:
        if target not in _ALLOWED_TRANSITIONS[self.current]:
            raise ValueError(
                f"illegal UX mutation proof transition: {self.current} -> {target}"
            )
        self.events.append(
            ProofTransitionEvent(
                event_id=f"{self.mutation_id}:transition:{len(self.events) + 1}",
                sequence=len(self.events) + 1,
                from_state=self.current,
                to_state=target,
                reason_code=reason,
            )
        )
        self.current = target


@dataclass(frozen=True)
class _PhaseResult:
    report: UXCampaignReport
    evidence: PhaseEvidence


class UXMutationProofRunner:
    def __init__(
        self,
        *,
        target_manager: TargetManager | None = None,
        shadow_runner: UXShadowRunner | None = None,
    ) -> None:
        self.target_manager = target_manager or TargetManager()
        self.shadow_runner = shadow_runner or UXShadowRunner()

    def validate(self, plan_file: str | Path) -> LoadedUXMutationProof:
        return load_ux_mutation_proof(plan_file)

    def run(
        self,
        plan_file: str | Path,
        *,
        workspace: str | Path,
        output_dir: str | Path,
        verify_replay: bool = True,
    ) -> UXMutationCampaignReport:
        loaded = load_ux_mutation_proof(plan_file)
        resolved_output = Path(output_dir).resolve()
        report = self._run_once(
            loaded,
            workspace=Path(workspace).resolve(),
            output_dir=resolved_output,
        )
        if verify_replay:
            with tempfile.TemporaryDirectory(prefix="ux-mutation-auto-replay-") as temp:
                replayed = self._run_once(
                    load_ux_mutation_proof(resolved_output / "input" / "plan.json"),
                    workspace=Path(temp) / "workspace",
                    output_dir=Path(temp) / "output",
                )
            if replayed.semantic_digest != report.semantic_digest:
                raise ValueError(
                    "automatic UX mutation replay drifted: "
                    f"expected={report.semantic_digest}, "
                    f"observed={replayed.semantic_digest}"
                )
            report = report.model_copy(
                update={
                    "metrics": report.metrics.model_copy(
                        update={"replay_percent": 100.0}
                    )
                }
            )
        self._write_report_and_manifests(resolved_output, report)
        return report

    def replay(
        self,
        bundle_dir: str | Path,
        *,
        workspace: str | Path,
    ) -> UXMutationCampaignReport:
        root = Path(bundle_dir).resolve()
        artifact_manifest = load_model(
            root / "artifact-manifest.json",
            UXMutationArtifactManifest,
        )
        replay_manifest = load_model(
            root / "replay-manifest.json",
            UXMutationReplayManifest,
        )
        if canonical_digest(artifact_manifest.files) != artifact_manifest.manifest_digest:
            raise ValueError("UX mutation artifact manifest digest mismatch")
        if artifact_manifest.manifest_digest != replay_manifest.artifact_manifest_digest:
            raise ValueError("UX mutation replay and artifact manifests differ")
        for relative, expected_hash in artifact_manifest.files.items():
            path = root / relative
            if not path.is_file():
                raise ValueError(f"UX mutation replay artifact is missing: {relative}")
            observed = sha256_file(path)
            if observed != expected_hash:
                raise ValueError(
                    f"UX mutation artifact hash mismatch for {relative}: "
                    f"expected={expected_hash}, observed={observed}"
                )
        for relative, expected_hash in replay_manifest.input_files.items():
            observed = sha256_file(root / relative)
            if observed != expected_hash:
                raise ValueError(f"UX mutation replay input changed: {relative}")

        with tempfile.TemporaryDirectory(prefix="ux-mutation-replay-") as temp:
            replayed = self._run_once(
                load_ux_mutation_proof(root / "input" / "plan.json"),
                workspace=Path(workspace).resolve(),
                output_dir=Path(temp) / "output",
            )
        if replayed.semantic_digest != replay_manifest.semantic_digest:
            raise ValueError(
                "independent UX mutation replay drifted: "
                f"expected={replay_manifest.semantic_digest}, "
                f"observed={replayed.semantic_digest}"
            )
        return replayed.model_copy(
            update={
                "metrics": replayed.metrics.model_copy(update={"replay_percent": 100.0})
            }
        )

    def _run_once(
        self,
        loaded: LoadedUXMutationProof,
        *,
        workspace: Path,
        output_dir: Path,
    ) -> UXMutationCampaignReport:
        self._prepare_empty_directory(output_dir, "UX mutation output")
        self._prepare_workspace(workspace, loaded.project_root)
        self._write_input_bundle(output_dir, loaded)

        results = tuple(
            self._run_mutation(
                loaded,
                mutation,
                workspace=workspace / mutation.mutation_id.lower(),
                evidence_root=output_dir / "mutations" / mutation.mutation_id,
                campaign_root=output_dir,
            )
            for mutation in loaded.selected_mutations
        )
        metrics = self._metrics(results, loaded)
        verdict = self._campaign_verdict(results)
        core = {
            "schema_version": "1.0",
            "campaign_id": loaded.plan.campaign_id,
            "spec_ref": loaded.plan.spec_ref,
            "parent_runtime_ref": loaded.plan.parent_runtime_ref,
            "mandate_ref": loaded.plan.mandate_ref,
            "mode": "SHADOW",
            "release_effect": "NONBLOCKING_SHADOW",
            "human_uat_required": True,
            "target_id": loaded.mutation_catalog.target.target_id,
            "target_revision": loaded.mutation_catalog.target.revision,
            "mutation_results": [item.model_dump(mode="json") for item in results],
            "metrics": metrics.model_copy(update={"replay_percent": 0.0}).model_dump(
                mode="json"
            ),
            "verdict": verdict.value,
        }
        return UXMutationCampaignReport(
            **core,
            metrics=metrics,
            semantic_digest=canonical_digest(core),
        )

    def _run_mutation(
        self,
        loaded: LoadedUXMutationProof,
        mutation: UXMutation,
        *,
        workspace: Path,
        evidence_root: Path,
        campaign_root: Path,
    ) -> MutationProofResult:
        recorder = _TransitionRecorder(mutation.mutation_id)
        evidence_root.mkdir(parents=True, exist_ok=True)
        baseline: PhaseEvidence | None = None
        mutated: PhaseEvidence | None = None
        restored: PhaseEvidence | None = None
        patch_evidence: PatchEvidence | None = None
        observed_failed: tuple[str, ...] = ()
        actor_consistent = False
        exact_restore = False
        failures: list[str] = []
        sandbox: TargetMutationSandbox | None = None

        try:
            target = self.target_manager.materialize(
                loaded.ux_campaign.target_manifest_path,
                workspace / "target",
                install=True,
            )
            if target.revision != loaded.mutation_catalog.target.revision:
                raise ValueError("materialized UX mutation target revision mismatch")
            sandbox = TargetMutationSandbox(target, mutation)
            sandbox.verify_clean_preimage()

            recorder.move(ProofState.BASELINE_RUNNING, "baseline_started")
            baseline_result = self._execute_phase(
                loaded,
                target,
                mutation,
                phase=ProofPhase.BASELINE,
                output_dir=evidence_root / "baseline",
                campaign_root=campaign_root,
            )
            baseline = baseline_result.evidence
            if baseline_result.report.verdict != UXVerdict.PASS:
                recorder.move(ProofState.BASELINE_FAILED, "baseline_not_pass")
                failures.append("baseline_not_proven")
                return self._result(
                    mutation,
                    recorder,
                    MutationOutcome.INVALID,
                    baseline,
                    patch_evidence,
                    mutated,
                    restored,
                    observed_failed,
                    actor_consistent,
                    exact_restore,
                    failures,
                    evidence_root,
                    campaign_root,
                )
            recorder.move(ProofState.BASELINE_PROVEN, "baseline_passed")

            recorder.move(ProofState.MUTATION_APPLYING, "exact_patch_started")
            sandbox.apply()
            recorder.move(ProofState.MUTATION_VERIFIED, "postimage_verified")

            recorder.move(ProofState.MUTATED_RUNNING, "mutated_phase_started")
            mutated_result = self._execute_phase(
                loaded,
                target,
                mutation,
                phase=ProofPhase.MUTATED,
                output_dir=evidence_root / "mutated",
                campaign_root=campaign_root,
            )
            mutated = mutated_result.evidence
            observed_failed = self._failed_checkpoint_union(mutated)
            killed = self._is_killed(mutation, mutated_result.report, observed_failed)
            if killed:
                recorder.move(
                    ProofState.MUTATION_KILLED,
                    "expected_oracle_failure_proven",
                )
                recorder.move(ProofState.RESTORING, "restore_started")
            else:
                failures.append("mutation_survived")
                recorder.move(
                    ProofState.RESTORING,
                    "mutation_survived_restore_started",
                )

            patch_evidence = sandbox.restore()
            exact_restore = patch_evidence.restore_clean
            recorder.move(ProofState.RESTORE_VERIFIED, "exact_restore_verified")

            if not killed:
                actor_consistent = self._actor_hashes_equal(baseline, mutated, None)
                if not actor_consistent:
                    recorder.move(ProofState.INVALID_EVIDENCE, "actor_input_hash_drift")
                    failures.append("actor_input_hash_drift")
                    return self._result(
                        mutation,
                        recorder,
                        MutationOutcome.INVALID,
                        baseline,
                        patch_evidence,
                        mutated,
                        restored,
                        observed_failed,
                        actor_consistent,
                        exact_restore,
                        failures,
                        evidence_root,
                        campaign_root,
                    )
                recorder.move(
                    ProofState.MUTATION_SURVIVED,
                    "expected_oracle_failure_missing",
                )
                return self._result(
                    mutation,
                    recorder,
                    MutationOutcome.SURVIVED,
                    baseline,
                    patch_evidence,
                    mutated,
                    restored,
                    observed_failed,
                    actor_consistent,
                    exact_restore,
                    failures,
                    evidence_root,
                    campaign_root,
                )

            recorder.move(ProofState.RESTORED_RUNNING, "restored_phase_started")
            restored_result = self._execute_phase(
                loaded,
                target,
                mutation,
                phase=ProofPhase.RESTORED,
                output_dir=evidence_root / "restored",
                campaign_root=campaign_root,
            )
            restored = restored_result.evidence
            actor_consistent = self._actor_hashes_equal(baseline, mutated, restored)
            if restored_result.report.verdict != UXVerdict.PASS:
                recorder.move(ProofState.RESTORE_FAILED, "restored_phase_not_pass")
                failures.append("restored_phase_failed")
                return self._result(
                    mutation,
                    recorder,
                    MutationOutcome.INVALID,
                    baseline,
                    patch_evidence,
                    mutated,
                    restored,
                    observed_failed,
                    actor_consistent,
                    exact_restore,
                    failures,
                    evidence_root,
                    campaign_root,
                )
            if not actor_consistent:
                recorder.move(ProofState.INVALID_EVIDENCE, "actor_input_hash_drift")
                failures.append("actor_input_hash_drift")
                return self._result(
                    mutation,
                    recorder,
                    MutationOutcome.INVALID,
                    baseline,
                    patch_evidence,
                    mutated,
                    restored,
                    observed_failed,
                    actor_consistent,
                    exact_restore,
                    failures,
                    evidence_root,
                    campaign_root,
                )
            recorder.move(ProofState.CLOSED_PASS, "mutation_proof_closed")
            return self._result(
                mutation,
                recorder,
                MutationOutcome.KILLED,
                baseline,
                patch_evidence,
                mutated,
                restored,
                observed_failed,
                actor_consistent,
                exact_restore,
                failures,
                evidence_root,
                campaign_root,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            failures.append(f"{type(exc).__name__}:{exc}")
            if sandbox is not None:
                try:
                    recovered = sandbox.recover_if_needed()
                    if recovered is not None:
                        patch_evidence = recovered
                        exact_restore = recovered.restore_clean
                except Exception as recovery_exc:  # recovery evidence must be preserved
                    failures.append(
                        "recovery_failed:"
                        f"{type(recovery_exc).__name__}:{recovery_exc}"
                    )
            outcome, terminal = self._failure_classification(recorder.current, baseline)
            if terminal in _ALLOWED_TRANSITIONS[recorder.current]:
                recorder.move(terminal, "runtime_or_evidence_boundary_failed")
            return self._result(
                mutation,
                recorder,
                outcome,
                baseline,
                patch_evidence,
                mutated,
                restored,
                observed_failed,
                actor_consistent,
                exact_restore,
                failures,
                evidence_root,
                campaign_root,
            )

    def _execute_phase(
        self,
        loaded: LoadedUXMutationProof,
        target: MaterializedTarget,
        mutation: UXMutation,
        *,
        phase: ProofPhase,
        output_dir: Path,
        campaign_root: Path,
    ) -> _PhaseResult:
        self._prepare_empty_directory(output_dir, f"{phase.value} phase output")
        selected_ids = tuple(
            ref.split("@", maxsplit=1)[0]
            for ref in mutation.affected_journey_refs
        )
        phase_plan = loaded.ux_campaign.plan.model_copy(
            update={
                "campaign_id": (
                    f"{loaded.plan.campaign_id}-{mutation.mutation_id.lower()}-"
                    f"{phase.value.lower()}"
                ),
                "journey_ids": selected_ids,
                "catalog_path": "catalog.yaml",
                "target_manifest_path": "target-manifest.yaml",
            }
        )
        phase_loaded = LoadedUXCampaign(
            plan=phase_plan,
            plan_path=output_dir / "input" / "campaign.json",
            catalog=loaded.ux_campaign.catalog,
            catalog_path=output_dir / "input" / "catalog.yaml",
            target_manifest=target.manifest,
            target_manifest_path=output_dir / "input" / "target-manifest.yaml",
        )
        input_dir = output_dir / "input"
        evidence_dir = output_dir / "evidence"
        input_dir.mkdir()
        evidence_dir.mkdir()
        dump_model(input_dir / "campaign.json", phase_plan)
        dump_model(input_dir / "catalog.yaml", phase_loaded.catalog)
        dump_model(input_dir / "target-manifest.yaml", phase_loaded.target_manifest)

        journeys = {item.journey_id: item for item in phase_loaded.catalog.journeys}
        profiles = {item.ref: item for item in phase_loaded.catalog.profiles}
        environments = {item.ref: item for item in phase_loaded.catalog.environments}
        expected_actor_hashes: dict[str, str] = {}
        runs = []

        with self.target_manager.process(
            target,
            log_dir=output_dir / "target-logs",
            timeout_seconds=30,
        ) as running:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    for journey_id in selected_ids:
                        journey = journeys[journey_id]
                        profile = profiles[journey.persona_refs[0]]
                        environment = environments[journey.environment_refs[0]]
                        actor_input = build_actor_input(journey, profile, environment)
                        actor_payload = actor_input.model_dump(mode="json")
                        leaked = _FORBIDDEN_ACTOR_KEYS.intersection(
                            _recursive_keys(actor_payload)
                        )
                        if leaked:
                            raise ValueError(
                                "mutation metadata leaked into actor input: "
                                f"{sorted(leaked)}"
                            )
                        expected_actor_hashes[journey.ref] = canonical_digest(
                            actor_payload
                        )
                        run = self.shadow_runner._execute_journey(
                            browser=browser,
                            base_url=running.base_url,
                            journey=journey,
                            profile=profile,
                            environment=environment,
                            target_revision=target.revision,
                            evidence_root=evidence_dir,
                        )
                        if run.actor_input_hash != expected_actor_hashes[journey.ref]:
                            raise ValueError(
                                "Synthetic User actor input hash was not reproducible"
                            )
                        runs.append(run)
                finally:
                    browser.close()

        report = self.shadow_runner._build_report(phase_plan, tuple(runs))
        dump_model(output_dir / "report.json", report)
        (output_dir / "report.md").write_text(
            self.shadow_runner.render_markdown(report),
            encoding="utf-8",
        )
        self.shadow_runner._write_manifests(output_dir, report)

        file_hash = sha256_file(target.app_dir / mutation.target_path)
        changes = changed_files(target.checkout_dir)
        failed = {
            run.journey_ref: tuple(
                key for key, passed in run.checkpoint_results.items() if not passed
            )
            for run in report.runs
        }
        evidence = PhaseEvidence(
            phase=phase,
            report_path=(output_dir / "report.json")
            .relative_to(campaign_root)
            .as_posix(),
            report_semantic_digest=report.semantic_digest,
            verdict=report.verdict.value,
            journey_refs=tuple(run.journey_ref for run in report.runs),
            actor_input_hashes={
                run.journey_ref: run.actor_input_hash for run in report.runs
            },
            failed_checkpoints=failed,
            target_file_sha256=file_hash,
            changed_files=changes,
            git_status_clean=not changes,
        )
        return _PhaseResult(report=report, evidence=evidence)

    @staticmethod
    def _is_killed(
        mutation: UXMutation,
        report: UXCampaignReport,
        observed_failed: tuple[str, ...],
    ) -> bool:
        if report.verdict != UXVerdict.FAIL:
            return False
        if not set(mutation.expected_failed_checkpoints).issubset(observed_failed):
            return False
        if any(
            run.evaluation.verdict in {UXVerdict.INVALID, UXVerdict.BLOCKED}
            for run in report.runs
        ):
            return False
        accepted_levels = (
            {"E4"}
            if mutation.minimum_evidence_level == "E4"
            else {"E3", "E4"}
        )
        return all(
            run.evaluation.evidence_level.value in accepted_levels
            for run in report.runs
        )

    @staticmethod
    def _failed_checkpoint_union(phase: PhaseEvidence) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    checkpoint
                    for checkpoints in phase.failed_checkpoints.values()
                    for checkpoint in checkpoints
                }
            )
        )

    @staticmethod
    def _actor_hashes_equal(
        baseline: PhaseEvidence | None,
        mutated: PhaseEvidence | None,
        restored: PhaseEvidence | None,
    ) -> bool:
        if baseline is None or mutated is None:
            return False
        if baseline.actor_input_hashes != mutated.actor_input_hashes:
            return False
        return (
            restored is None
            or baseline.actor_input_hashes == restored.actor_input_hashes
        )

    @staticmethod
    def _failure_classification(
        current: ProofState,
        baseline: PhaseEvidence | None,
    ) -> tuple[MutationOutcome, ProofState]:
        if baseline is None:
            return MutationOutcome.BLOCKED, ProofState.BLOCKED
        if current == ProofState.MUTATION_APPLYING:
            return MutationOutcome.INVALID, ProofState.MUTATION_APPLY_FAILED
        if current in {ProofState.RESTORING, ProofState.RESTORED_RUNNING}:
            return MutationOutcome.INVALID, ProofState.RESTORE_FAILED
        return MutationOutcome.INVALID, ProofState.INVALID_EVIDENCE

    @staticmethod
    def _result(
        mutation: UXMutation,
        recorder: _TransitionRecorder,
        outcome: MutationOutcome,
        baseline: PhaseEvidence | None,
        patch: PatchEvidence | None,
        mutated: PhaseEvidence | None,
        restored: PhaseEvidence | None,
        observed_failed: tuple[str, ...],
        actor_consistent: bool,
        exact_restore: bool,
        failures: list[str],
        evidence_root: Path,
        campaign_root: Path,
    ) -> MutationProofResult:
        return MutationProofResult(
            mutation_id=mutation.mutation_id,
            family=mutation.family,
            title=mutation.title,
            outcome=outcome,
            terminal_state=recorder.current,
            transitions=tuple(recorder.events),
            baseline=baseline,
            patch=patch,
            mutated=mutated,
            restored=restored,
            expected_failed_checkpoints=mutation.expected_failed_checkpoints,
            observed_failed_checkpoints=observed_failed,
            expected_failure_classification=mutation.expected_failure_classification,
            actor_input_consistent=actor_consistent,
            exact_restore=exact_restore,
            failures=tuple(failures),
            evidence_path=evidence_root.relative_to(campaign_root).as_posix(),
        )

    @staticmethod
    def _metrics(
        results: tuple[MutationProofResult, ...],
        loaded: LoadedUXMutationProof,
    ) -> MutationCampaignMetrics:
        total = len(results)
        killed = sum(item.outcome == MutationOutcome.KILLED for item in results)
        survived = sum(item.outcome == MutationOutcome.SURVIVED for item in results)
        invalid = sum(item.outcome == MutationOutcome.INVALID for item in results)
        blocked = sum(item.outcome == MutationOutcome.BLOCKED for item in results)
        exact = sum(item.exact_restore for item in results)
        baseline_false_positive = sum(
            item.baseline is not None
            and item.baseline.verdict != UXVerdict.PASS.value
            for item in results
        )
        expected_oracles = {
            oracle
            for mutation in loaded.selected_mutations
            for oracle in mutation.oracle_refs
        }
        covered_oracles = {
            oracle
            for mutation, result in zip(
                loaded.selected_mutations,
                results,
                strict=True,
            )
            if result.outcome == MutationOutcome.KILLED
            for oracle in mutation.oracle_refs
        }
        expected_journeys = {
            journey
            for mutation in loaded.selected_mutations
            for journey in mutation.affected_journey_refs
        }
        covered_journeys = {
            journey
            for mutation, result in zip(
                loaded.selected_mutations,
                results,
                strict=True,
            )
            if result.outcome == MutationOutcome.KILLED
            for journey in mutation.affected_journey_refs
        }
        return MutationCampaignMetrics(
            total_mutations=total,
            killed_mutations=killed,
            survived_mutations=survived,
            invalid_mutations=invalid,
            blocked_mutations=blocked,
            critical_mutation_kill_rate_percent=_percent(killed, total),
            baseline_false_positive_count=baseline_false_positive,
            critical_false_green_count=survived,
            exact_restore_percent=_percent(exact, total),
            replay_percent=0.0,
            oracle_clause_coverage_percent=_percent(
                len(covered_oracles),
                len(expected_oracles),
            ),
            journey_coverage_percent=_percent(
                len(covered_journeys),
                len(expected_journeys),
            ),
            hidden_metadata_leakage_count=sum(
                "metadata leaked" in failure
                for item in results
                for failure in item.failures
            ),
            undeclared_changed_files_count=sum(
                "undeclared files" in failure
                for item in results
                for failure in item.failures
            ),
            ai_only_kill_count=0,
        )

    @staticmethod
    def _campaign_verdict(
        results: Sequence[MutationProofResult],
    ) -> ProofCampaignVerdict:
        outcomes = {item.outcome for item in results}
        if MutationOutcome.INVALID in outcomes:
            return ProofCampaignVerdict.INVALID
        if MutationOutcome.BLOCKED in outcomes:
            return ProofCampaignVerdict.BLOCKED
        if MutationOutcome.SURVIVED in outcomes:
            return ProofCampaignVerdict.FAIL
        return ProofCampaignVerdict.PASS

    @staticmethod
    def _prepare_empty_directory(path: Path, label: str) -> None:
        if path.exists() and any(path.iterdir()):
            raise ValueError(f"{label} must be empty: {path}")
        path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _prepare_workspace(workspace: Path, project_root: Path) -> None:
        resolved_root = project_root.resolve()
        if (
            workspace == resolved_root
            or workspace.is_relative_to(resolved_root)
            or resolved_root.is_relative_to(workspace)
        ):
            raise ValueError(
                "UX mutation workspace must be isolated from the repository tree"
            )
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _write_input_bundle(root: Path, loaded: LoadedUXMutationProof) -> None:
        input_dir = root / "input"
        input_dir.mkdir()
        normalized_plan = loaded.plan.model_copy(
            update={
                "project_root": ".",
                "mutation_catalog_path": "mutation-catalog.yaml",
                "ux_campaign_path": "ux-campaign.json",
            }
        )
        normalized_ux_plan = loaded.ux_campaign.plan.model_copy(
            update={
                "catalog_path": "ux-catalog.yaml",
                "target_manifest_path": "target-manifest.yaml",
            }
        )
        dump_model(input_dir / "plan.json", normalized_plan)
        dump_model(input_dir / "mutation-catalog.yaml", loaded.mutation_catalog)
        dump_model(input_dir / "ux-campaign.json", normalized_ux_plan)
        dump_model(input_dir / "ux-catalog.yaml", loaded.ux_campaign.catalog)
        dump_model(
            input_dir / "target-manifest.yaml",
            loaded.ux_campaign.target_manifest,
        )

    @staticmethod
    def _write_report_and_manifests(
        root: Path,
        report: UXMutationCampaignReport,
    ) -> None:
        dump_model(root / "report.json", report)
        (root / "report.md").write_text(
            UXMutationProofRunner.render_markdown(report),
            encoding="utf-8",
        )
        excluded = {"artifact-manifest.json", "replay-manifest.json"}
        files = {
            path.relative_to(root).as_posix(): sha256_file(path)
            for path in sorted(item for item in root.rglob("*") if item.is_file())
            if path.name not in excluded
        }
        manifest_digest = canonical_digest(files)
        dump_model(
            root / "artifact-manifest.json",
            UXMutationArtifactManifest(
                campaign_id=report.campaign_id,
                files=files,
                manifest_digest=manifest_digest,
            ),
        )
        dump_model(
            root / "replay-manifest.json",
            UXMutationReplayManifest(
                campaign_id=report.campaign_id,
                spec_ref=report.spec_ref,
                parent_runtime_ref=report.parent_runtime_ref,
                semantic_digest=report.semantic_digest,
                artifact_manifest_digest=manifest_digest,
                input_files={
                    relative: digest
                    for relative, digest in files.items()
                    if relative.startswith("input/")
                },
            ),
        )

    @staticmethod
    def render_markdown(report: UXMutationCampaignReport) -> str:
        lines = [
            f"# UX Mutation Proof: {report.campaign_id}",
            "",
            f"- Verdict: `{report.verdict.value}`",
            f"- Runtime mode: `{report.mode}`",
            f"- Release effect: `{report.release_effect}`",
            f"- Human UAT required: `{report.human_uat_required}`",
            f"- Target revision: `{report.target_revision}`",
            (
                "- Mutations killed: "
                f"`{report.metrics.killed_mutations}/"
                f"{report.metrics.total_mutations}`"
            ),
            (
                "- Critical False Green: "
                f"`{report.metrics.critical_false_green_count}`"
            ),
            f"- Exact restore: `{report.metrics.exact_restore_percent:.0f}%`",
            f"- Independent replay: `{report.metrics.replay_percent:.0f}%`",
            f"- Semantic digest: `{report.semantic_digest}`",
            "",
            "| Mutation | Family | Outcome | Failed checkpoints | Restore |",
            "|---|---|---|---|---|",
        ]
        for result in report.mutation_results:
            lines.append(
                f"| {result.mutation_id} | {result.family.value} | "
                f"{result.outcome.value} | "
                f"{', '.join(result.observed_failed_checkpoints) or '-'} | "
                f"{'PASS' if result.exact_restore else 'FAIL'} |"
            )
        lines.extend(
            [
                "",
                (
                    "This proof remains SHADOW evidence. Advisory/Blocking are "
                    "disabled and Human UAT remains required."
                ),
            ]
        )
        return "\n".join(lines) + "\n"


def _recursive_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        keys = set(value)
        for nested in value.values():
            keys.update(_recursive_keys(nested))
        return keys
    if isinstance(value, list | tuple):
        keys: set[str] = set()
        for nested in value:
            keys.update(_recursive_keys(nested))
        return keys
    return set()


def _percent(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        raise ValueError("UX mutation proof percentage denominator must be positive")
    return numerator / denominator * 100.0
