from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..adapters.todomvc import TodoMVCAdapter
from .evaluator import canonical_digest
from .models import InteractionKind, JourneyExecutor, UXEvent, UXJourney, UXMetrics
from .semantic_state import focus_snapshot, normalized_todo_state


class TodoMVCJourneyExecutor:
    def __init__(self, page: Any, trace_relative: Path) -> None:
        self.page = page
        self.trace_relative = trace_relative
        self.adapter = TodoMVCAdapter()
        self.events: list[UXEvent] = []

    def prepare(self) -> None:
        self.adapter.clear(self.page)
        state = self.state()
        self.append_event(
            kind=InteractionKind.NAVIGATE,
            target="page:todomvc",
            before=state,
            after=state,
            result="Pinned TodoMVC target is visible with a clean synthetic fixture.",
        )

    def run(self, journey: UXJourney) -> dict[str, Any]:
        if journey.executor == JourneyExecutor.TODO_ADD:
            return self.todo_add()
        if journey.executor == JourneyExecutor.TODO_RETURNING_FILTER_PERSISTENCE:
            return self.todo_returning_filter_persistence()
        if journey.executor == JourneyExecutor.TODO_KEYBOARD_PRIMARY:
            return self.todo_keyboard_primary()
        if journey.executor == JourneyExecutor.TODO_INTERRUPTED_RESUME:
            return self.todo_interrupted_resume()
        raise ValueError(f"unsupported UX journey executor: {journey.executor}")

    def state(self) -> dict[str, Any]:
        return normalized_todo_state(self.page, self.adapter)

    def append_event(
        self,
        *,
        kind: InteractionKind,
        target: str,
        before: Mapping[str, Any],
        after: Mapping[str, Any],
        result: str,
    ) -> None:
        sequence = len(self.events) + 1
        self.events.append(
            UXEvent(
                event_id=f"ux-event-{sequence:03d}",
                sequence=sequence,
                kind=kind,
                semantic_target_ref=target,
                before_state_hash=canonical_digest(before),
                after_state_hash=canonical_digest(after),
                observable_result=result,
                evidence_refs=(self.trace_relative.as_posix(),),
            )
        )

    def _settle_filter_route(self) -> None:
        self.page.wait_for_function(
            "() => ['#/completed', '#/active'].includes(window.location.hash)"
        )
        self.page.evaluate(
            """
            () => new Promise((resolve) => {
                requestAnimationFrame(() => requestAnimationFrame(resolve));
            })
            """
        )

    def todo_add(self) -> dict[str, Any]:
        new_todo = self.page.locator(".new-todo")
        discoverable = new_todo.is_visible() and bool(new_todo.get_attribute("placeholder"))
        before = self.state()
        new_todo.fill("Plan UX review")
        new_todo.press("Enter")
        new_todo.blur()
        after = self.state()
        self.append_event(
            kind=InteractionKind.ACTION_SUCCEEDED,
            target="todo:new-input",
            before=before,
            after=after,
            result="Submitted one task through the visible primary input.",
        )
        labels = self.page.locator(".todo-list li:visible label").all_text_contents()
        count_text = self.page.locator(".todo-count").inner_text()
        visible = labels == ["Plan UX review"]
        count_ok = "1 item left" in count_text
        self.append_event(
            kind=InteractionKind.FEEDBACK_OBSERVED,
            target="todo:list-and-count",
            before=after,
            after=self.state(),
            result=f"labels={labels}; count={count_text!r}",
        )
        return {
            "entry_field_is_discoverable": discoverable,
            "task_is_visible_after_submit": visible,
            "remaining_count_is_consistent": count_ok,
            "feedback_observed": visible and count_ok,
            "task_completed": visible and count_ok,
        }

    def todo_returning_filter_persistence(self) -> dict[str, Any]:
        for title in ("Completed journey", "Active journey"):
            before = self.state()
            self.page.locator(".new-todo").fill(title)
            self.page.locator(".new-todo").press("Enter")
            after = self.state()
            self.append_event(
                kind=InteractionKind.ACTION_SUCCEEDED,
                target="todo:new-input",
                before=before,
                after=after,
                result=f"Added {title!r}.",
            )
        before_complete = self.state()
        self.page.locator(".todo-list li").first.locator(".toggle").check()
        after_complete = self.state()
        self.append_event(
            kind=InteractionKind.ACTION_SUCCEEDED,
            target="todo:first-toggle",
            before=before_complete,
            after=after_complete,
            result="Completed the first task.",
        )
        self.page.get_by_role("link", name="Completed").click()
        self._settle_filter_route()
        completed_labels = self.page.locator(
            ".todo-list li:visible label"
        ).all_text_contents()
        filter_ok = completed_labels == ["Completed journey"]
        self.page.reload(wait_until="domcontentloaded")
        self._settle_filter_route()
        state = self.adapter.read(self.page)
        persistence_ok = len(state.items) == 2 and state.items[0].completed
        route_ok = self.page.url.endswith("#/completed")
        self.append_event(
            kind=InteractionKind.RECOVERY_SUCCEEDED,
            target="page:reload",
            before=after_complete,
            after=self.state(),
            result=(
                f"completed_labels={completed_labels}; persisted={persistence_ok}; "
                f"route_preserved={route_ok}"
            ),
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

    def todo_keyboard_primary(self) -> dict[str, Any]:
        input_box = self.page.locator(".new-todo")
        input_box.focus()
        focused = focus_snapshot(self.page)
        before = self.state()
        self.page.keyboard.type("Keyboard journey")
        self.page.keyboard.press("Enter")
        after = self.state()
        labels = self.page.locator(".todo-list li:visible label").all_text_contents()
        semantic_name = input_box.get_attribute("aria-label") or input_box.get_attribute(
            "placeholder"
        )
        focus_reached = focused.get("class") == "new-todo"
        completed = labels == ["Keyboard journey"]
        self.append_event(
            kind=InteractionKind.FOCUS_CHANGED,
            target="todo:new-input",
            before=before,
            after=after,
            result=(
                f"keyboard_only=True; focus={focused}; "
                f"semantic_name={semantic_name!r}; labels={labels}"
            ),
        )
        return {
            "focus_reaches_input": focus_reached,
            "task_can_be_submitted": completed,
            "semantic_name_is_present": bool(semantic_name),
            "keyboard_primary_action_completes": completed,
            "feedback_observed": completed,
            "keyboard_completion": completed,
            "semantic_accessibility_failures": 0 if semantic_name else 1,
            "focus_order_violations": 0 if focus_reached else 1,
            "task_completed": completed,
        }

    def todo_interrupted_resume(self) -> dict[str, Any]:
        before = self.state()
        self.page.locator(".new-todo").fill("Resume after interruption")
        self.page.locator(".new-todo").press("Enter")
        submitted = self.state()
        self.append_event(
            kind=InteractionKind.ACTION_SUCCEEDED,
            target="todo:new-input",
            before=before,
            after=submitted,
            result="Added a task before interruption.",
        )
        self.page.reload(wait_until="domcontentloaded")
        state = self.adapter.read(self.page)
        labels = self.page.locator(".todo-list li:visible label").all_text_contents()
        resumed = len(state.items) == 1 and labels == ["Resume after interruption"]
        self.append_event(
            kind=InteractionKind.RECOVERY_SUCCEEDED,
            target="page:interruption-reload",
            before=submitted,
            after=self.state(),
            result=f"persisted_items={len(state.items)}; labels={labels}",
        )
        return {
            "task_exists_before_interruption": True,
            "task_persists_after_reload": resumed,
            "visible_state_matches_storage": resumed,
            "feedback_observed": resumed,
            "recovery_success": resumed,
            "task_completed": resumed,
        }


def metrics_for(
    journey: UXJourney,
    checkpoints: Mapping[str, bool],
    observations: Mapping[str, Any],
    events: Sequence[UXEvent],
) -> UXMetrics:
    action_kinds = {
        InteractionKind.ACTION_ATTEMPTED,
        InteractionKind.ACTION_SUCCEEDED,
        InteractionKind.ACTION_FAILED,
        InteractionKind.RECOVERY_ATTEMPTED,
        InteractionKind.RECOVERY_SUCCEEDED,
    }
    return UXMetrics(
        task_completed=bool(observations.get("task_completed", False)),
        checkpoint_completed=sum(checkpoints.values()),
        checkpoint_total=len(journey.oracle.required_checkpoints),
        step_count=sum(event.kind in action_kinds for event in events),
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
