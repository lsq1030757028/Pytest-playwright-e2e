from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..adapters.todomvc import TodoMVCAdapter
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
from .models import (
    ActorJourneyInput,
    EvidenceLevel,
    ExperienceEnvironment,
    InteractionKind,
    JourneyExecutor,
    SyntheticUserProfile,
    UXArtifactManifest,
    UXCampaignPlan,
    UXCampaignReport,
    UXCatalog,
    UXEvaluation,
    UXEvent,
    UXJourney,
    UXJourneyRun,
    UXMetrics,
    UXReplayManifest,
    UXVerdict,
)


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
        target_dir = workspace_root / "target"
        target_manager = TargetManager()
        target = target_manager.materialize(
            loaded.target_manifest_path,
            target_dir,
            install=True,
        )
        selected_ids = self._selected_ids(loaded.plan, loaded.catalog)
        journey_map = {item.journey_id: item for item in loaded.catalog.journeys}
        profile_map = {item.ref: item for item in loaded.catalog.profiles}
        environment_map = {item.ref: item for item in loaded.catalog.environments}
        runs: list[UXJourneyRun] = []

        log_dir = root / "target-logs"
        with target_manager.process(target, log_dir=log_dir) as running:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    for journey_id in selected_ids:
                        journey = journey_map[journey_id]
                        profile = profile_map[journey.persona_refs[0]]
                        environment = environment_map[journey.environment_refs[0]]
                        runs.append(
                            self._execute_journey(
                                browser=browser,
                                base_url=running.base_url,
                                journey=journey,
                                profile=profile,
                                environment=environment,
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
        actor_input = build_actor_input(journey, profile, environment)
        journey_dir = evidence_root / journey.journey_id
        journey_dir.mkdir(parents=True, exist_ok=True)
        trace_relative = Path("evidence") / journey.journey_id / "trace.zip"
        screenshot_relative = Path("evidence") / journey.journey_id / "final.png"
        semantic_relative = Path("evidence") / journey.journey_id / "semantic.json"
        trace_path = journey_dir / "trace.zip"
        screenshot_path = journey_dir / "final.png"
        semantic_path = journey_dir / "semantic.json"

        reduced_motion = (
            "reduce" if environment.device_profile.prefers_reduced_motion else "no-preference"
        )
        context = browser.new_context(
            viewport={
                "width": environment.device_profile.viewport_width,
                "height": environment.device_profile.viewport_height,
            },
            device_scale_factor=environment.device_profile.device_scale_factor,
            locale=environment.locale_timezone.locale,
            timezone_id=environment.locale_timezone.timezone,
            reduced_motion=reduced_motion,
        )
        context.tracing.start(screenshots=True, snapshots=True, sources=False)
        page = context.new_page()
        adapter = TodoMVCAdapter()
        events: list[UXEvent] = []
        checkpoint_results: dict[str, bool] = {}
        runtime_error: str | None = None
        observations: dict[str, Any] = {}
        try:
            page.goto(base_url, wait_until="domcontentloaded")
            adapter.clear(page)
            self._append_event(
                events,
                kind=InteractionKind.NAVIGATE,
                target="page:todomvc",
                before=self._state_payload(page, adapter),
                after=self._state_payload(page, adapter),
                result="Pinned TodoMVC target is visible with a clean synthetic fixture.",
                evidence_refs=(trace_relative.as_posix(),),
            )
            observations = self._run_executor(page, adapter, journey, events, trace_relative)
            checkpoint_results = {
                checkpoint: bool(observations.get(checkpoint, False))
                for checkpoint in journey.oracle.required_checkpoints
            }
        except Exception as exc:  # real boundary failures become evidence, not false PASS
            runtime_error = f"{type(exc).__name__}: {exc}"
            state = self._safe_state_payload(page, adapter)
            self._append_event(
                events,
                kind=InteractionKind.ACTION_FAILED,
                target=f"journey:{journey.journey_id}",
                before=state,
                after=state,
                result=runtime_error,
                evidence_refs=(trace_relative.as_posix(),),
            )
        finally:
            semantic_path.write_text(
                json.dumps(self._semantic_snapshot(page), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            page.screenshot(path=str(screenshot_path), full_page=True)
            context.tracing.stop(path=str(trace_path))
            context.close()

        metrics = self._metrics(journey, checkpoint_results, observations, events)
        if runtime_error is not None:
            evaluation = UXEvaluation(
                verdict=UXVerdict.INVALID,
                evidence_level=EvidenceLevel.E3,
                failures=(f"runtime_boundary_error:{runtime_error}",),
                blocker=False,
            )
        else:
            evaluation = evaluate_journey(journey, checkpoint_results, metrics)
        evidence_refs = (
            trace_relative.as_posix(),
            screenshot_relative.as_posix(),
            semantic_relative.as_posix(),
        )
        critic = RuleBasedUXCritic()
        findings = critic.propose(
            journey=journey,
            metrics=metrics,
            event_refs=tuple(item.event_id for item in events),
            evidence_refs=evidence_refs,
        )
        run_id = f"ux0-todomvc-shadow:{journey.journey_id}:1"
        evidence_path = (Path("evidence") / journey.journey_id).as_posix()
        return UXJourneyRun(
            run_id=run_id,
            journey_ref=journey.ref,
            profile_ref=profile.ref,
            environment_ref=environment.ref,
            environment_hash=environment_digest(environment),
            actor_input_hash=canonical_digest(actor_input.model_dump(mode="json")),
            target_revision=target_revision,
            events=tuple(events),
            checkpoint_results=checkpoint_results,
            metrics=metrics,
            findings=findings,
            evaluation=evaluation,
            evidence_path=evidence_path,
        )

    def _run_executor(
        self,
        page: Any,
        adapter: TodoMVCAdapter,
        journey: UXJourney,
        events: list[UXEvent],
        trace_relative: Path,
    ) -> dict[str, Any]:
        if journey.executor == JourneyExecutor.TODO_ADD:
            return self._todo_add(page, adapter, events, trace_relative)
        if journey.executor == JourneyExecutor.TODO_RETURNING_FILTER_PERSISTENCE:
            return self._todo_returning(page, adapter, events, trace_relative)
        if journey.executor == JourneyExecutor.TODO_KEYBOARD_PRIMARY:
            return self._todo_keyboard(page, adapter, events, trace_relative)
        if journey.executor == JourneyExecutor.TODO_INTERRUPTED_RESUME:
            return self._todo_interrupted(page, adapter, events, trace_relative)
        raise ValueError(f"unsupported UX journey executor: {journey.executor}")

    def _todo_add(
        self, page: Any, adapter: TodoMVCAdapter, events: list[UXEvent], trace: Path
    ) -> dict[str, Any]:
        new_todo = page.locator(".new-todo")
        discoverable = new_todo.is_visible() and bool(new_todo.get_attribute("placeholder"))
        before = self._state_payload(page, adapter)
        new_todo.fill("Plan UX review")
        new_todo.press("Enter")
        new_todo.blur()
        after = self._state_payload(page, adapter)
        self._append_event(
            events,
            kind=InteractionKind.ACTION_SUCCEEDED,
            target="todo:new-input",
            before=before,
            after=after,
            result="Submitted one task through the visible primary input.",
            evidence_refs=(trace.as_posix(),),
        )
        labels = page.locator(".todo-list li:visible label").all_text_contents()
        count_text = page.locator(".todo-count").inner_text()
        visible = labels == ["Plan UX review"]
        count_ok = "1 item left" in count_text
        self._append_event(
            events,
            kind=InteractionKind.FEEDBACK_OBSERVED,
            target="todo:list-and-count",
            before=after,
            after=self._state_payload(page, adapter),
            result=f"labels={labels}; count={count_text!r}",
            evidence_refs=(trace.as_posix(),),
        )
        return {
            "entry_field_is_discoverable": discoverable,
            "task_is_visible_after_submit": visible,
            "remaining_count_is_consistent": count_ok,
            "feedback_observed": visible and count_ok,
            "task_completed": visible and count_ok,
        }

    def _todo_returning(
        self, page: Any, adapter: TodoMVCAdapter, events: list[UXEvent], trace: Path
    ) -> dict[str, Any]:
        for title in ("Completed journey", "Active journey"):
            before = self._state_payload(page, adapter)
            page.locator(".new-todo").fill(title)
            page.locator(".new-todo").press("Enter")
            after = self._state_payload(page, adapter)
            self._append_event(
                events,
                kind=InteractionKind.ACTION_SUCCEEDED,
                target="todo:new-input",
                before=before,
                after=after,
                result=f"Added {title!r}.",
                evidence_refs=(trace.as_posix(),),
            )
        before_complete = self._state_payload(page, adapter)
        page.locator(".todo-list li").first.locator(".toggle").check()
        after_complete = self._state_payload(page, adapter)
        self._append_event(
            events,
            kind=InteractionKind.ACTION_SUCCEEDED,
            target="todo:first-toggle",
            before=before_complete,
            after=after_complete,
            result="Completed the first task.",
            evidence_refs=(trace.as_posix(),),
        )
        page.get_by_role("link", name="Completed").click()
        completed_labels = page.locator(".todo-list li:visible label").all_text_contents()
        filter_ok = completed_labels == ["Completed journey"]
        page.reload(wait_until="domcontentloaded")
        state = adapter.read(page)
        persistence_ok = len(state.items) == 2 and state.items[0].completed
        route_ok = page.url.endswith("#/completed")
        self._append_event(
            events,
            kind=InteractionKind.RECOVERY_SUCCEEDED,
            target="page:reload",
            before=after_complete,
            after=self._state_payload(page, adapter),
            result=(
                f"completed_labels={completed_labels}; persisted={persistence_ok}; "
                f"route_preserved={route_ok}"
            ),
            evidence_refs=(trace.as_posix(),),
        )
        return {
            "task_can_be_completed": state.items[0].completed if state.items else False,
            "completed_filter_is_consistent": filter_ok,
            "state_persists_after_reload": persistence_ok,
            "filter_route_persists_after_reload": route_ok,
            "feedback_observed": filter_ok,
            "recovery_success": persistence_ok and route_ok,
            "task_completed": filter_ok and persistence_ok,
        }

    def _todo_keyboard(
        self, page: Any, adapter: TodoMVCAdapter, events: list[UXEvent], trace: Path
    ) -> dict[str, Any]:
        input_box = page.locator(".new-todo")
        input_box.focus()
        focus_before = self._focus_snapshot(page)
        before = self._state_payload(page, adapter)
        page.keyboard.type("Keyboard journey")
        page.keyboard.press("Enter")
        after = self._state_payload(page, adapter)
        labels = page.locator(".todo-list li:visible label").all_text_contents()
        semantic_name = input_box.get_attribute("aria-label") or input_box.get_attribute(
            "placeholder"
        )
        focus_visible = focus_before.get("class") == "new-todo"
        completed = labels == ["Keyboard journey"]
        self._append_event(
            events,
            kind=InteractionKind.FOCUS_CHANGED,
            target="todo:new-input",
            before=before,
            after=after,
            result=(
                f"keyboard_only=True; focus={focus_before}; "
                f"semantic_name={semantic_name!r}; labels={labels}"
            ),
            evidence_refs=(trace.as_posix(),),
        )
        return {
            "focus_reaches_input": focus_visible,
            "task_can_be_submitted": completed,
            "semantic_name_is_present": bool(semantic_name),
            "keyboard_primary_action_completes": completed,
            "feedback_observed": completed,
            "keyboard_completion": completed,
            "semantic_accessibility_failures": 0 if semantic_name else 1,
            "focus_order_violations": 0 if focus_visible else 1,
            "task_completed": completed,
        }

    def _todo_interrupted(
        self, page: Any, adapter: TodoMVCAdapter, events: list[UXEvent], trace: Path
    ) -> dict[str, Any]:
        before = self._state_payload(page, adapter)
        page.locator(".new-todo").fill("Resume after interruption")
        page.locator(".new-todo").press("Enter")
        submitted = self._state_payload(page, adapter)
        self._append_event(
            events,
            kind=InteractionKind.ACTION_SUCCEEDED,
            target="todo:new-input",
            before=before,
            after=submitted,
            result="Added a task before interruption.",
            evidence_refs=(trace.as_posix(),),
        )
        page.reload(wait_until="domcontentloaded")
        state = adapter.read(page)
        labels = page.locator(".todo-list li:visible label").all_text_contents()
        resumed = len(state.items) == 1 and labels == ["Resume after interruption"]
        self._append_event(
            events,
            kind=InteractionKind.RECOVERY_SUCCEEDED,
            target="page:interruption-reload",
            before=submitted,
            after=self._state_payload(page, adapter),
            result=f"persisted_items={len(state.items)}; labels={labels}",
            evidence_refs=(trace.as_posix(),),
        )
        return {
            "task_exists_before_interruption": True,
            "task_persists_after_reload": resumed,
            "visible_state_matches_storage": resumed,
            "feedback_observed": resumed,
            "recovery_success": resumed,
            "task_completed": resumed,
        }

    @staticmethod
    def _metrics(
        journey: UXJourney,
        checkpoints: Mapping[str, bool],
        observations: Mapping[str, Any],
        events: Sequence[UXEvent],
    ) -> UXMetrics:
        return UXMetrics(
            task_completed=bool(observations.get("task_completed", False)),
            checkpoint_completed=sum(checkpoints.values()),
            checkpoint_total=len(journey.oracle.required_checkpoints),
            step_count=sum(
                event.kind
                in {
                    InteractionKind.ACTION_ATTEMPTED,
                    InteractionKind.ACTION_SUCCEEDED,
                    InteractionKind.ACTION_FAILED,
                    InteractionKind.RECOVERY_ATTEMPTED,
                    InteractionKind.RECOVERY_SUCCEEDED,
                }
                for event in events
            ),
            backtrack_count=sum(event.kind == InteractionKind.BACKTRACK for event in events),
            repeated_action_count=sum(
                event.kind == InteractionKind.REPEAT_ACTION for event in events
            ),
            dead_end_count=sum(event.kind == InteractionKind.DEAD_END for event in events),
            recovery_success=observations.get("recovery_success"),
            feedback_observed=bool(observations.get("feedback_observed", False)),
            keyboard_completion=observations.get("keyboard_completion"),
            focus_order_violations=int(observations.get("focus_order_violations", 0)),
            semantic_accessibility_failures=int(
                observations.get("semantic_accessibility_failures", 0)
            ),
            unexpected_state_loss=bool(observations.get("unexpected_state_loss", False)),
        )

    @staticmethod
    def _append_event(
        events: list[UXEvent],
        *,
        kind: InteractionKind,
        target: str,
        before: Mapping[str, Any],
        after: Mapping[str, Any],
        result: str,
        evidence_refs: tuple[str, ...],
    ) -> None:
        sequence = len(events) + 1
        events.append(
            UXEvent(
                event_id=f"ux-event-{sequence:03d}",
                sequence=sequence,
                kind=kind,
                semantic_target_ref=target,
                before_state_hash=canonical_digest(before),
                after_state_hash=canonical_digest(after),
                observable_result=result,
                evidence_refs=evidence_refs,
            )
        )

    @staticmethod
    def _state_payload(page: Any, adapter: TodoMVCAdapter) -> dict[str, Any]:
        state = adapter.read(page).model_dump(mode="json")
        return {
            "storage": state,
            "visible_labels": page.locator(".todo-list li:visible label").all_text_contents(),
            "remaining_count": (
                page.locator(".todo-count").inner_text()
                if page.locator(".todo-count").count()
                else ""
            ),
            "route": page.url.split("#", maxsplit=1)[1] if "#" in page.url else "",
            "focus": UXShadowRunner._focus_snapshot(page),
        }

    @staticmethod
    def _safe_state_payload(page: Any, adapter: TodoMVCAdapter) -> dict[str, Any]:
        try:
            return UXShadowRunner._state_payload(page, adapter)
        except Exception as exc:
            return {"state_unavailable": f"{type(exc).__name__}:{exc}"}

    @staticmethod
    def _focus_snapshot(page: Any) -> dict[str, Any]:
        return page.evaluate(
            """() => {
                const el = document.activeElement;
                if (!el) return {};
                return {
                    tag: el.tagName.toLowerCase(),
                    class: el.className || '',
                    role: el.getAttribute('role') || '',
                    ariaLabel: el.getAttribute('aria-label') || '',
                    placeholder: el.getAttribute('placeholder') || ''
                };
            }"""
        )

    @staticmethod
    def _semantic_snapshot(page: Any) -> dict[str, Any]:
        elements = page.locator("input,button,a,[role]").evaluate_all(
            """elements => elements.map((el, index) => ({
                index,
                tag: el.tagName.toLowerCase(),
                role: el.getAttribute('role') || '',
                ariaLabel: el.getAttribute('aria-label') || '',
                placeholder: el.getAttribute('placeholder') || '',
                text: (el.innerText || '').trim(),
                type: el.getAttribute('type') || '',
                tabindex: el.getAttribute('tabindex') || '',
                disabled: Boolean(el.disabled),
                visible: Boolean(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
            }))"""
        )
        return {
            "elements": elements,
            "active_element": UXShadowRunner._focus_snapshot(page),
        }

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
