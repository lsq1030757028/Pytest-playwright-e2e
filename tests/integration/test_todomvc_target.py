from __future__ import annotations

import os
from pathlib import Path

import playwright.sync_api
import pytest

from test_workflow.adapters.todomvc import TodoItem, TodoMVCAdapter
from test_workflow.targets import TargetManager


REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET_MANIFEST = REPO_ROOT / "targets" / "percy-example-todomvc" / "target.yaml"


@pytest.mark.target_integration
@pytest.mark.skipif(
    os.getenv("RUN_TARGET_INTEGRATION") != "1",
    reason="Set RUN_TARGET_INTEGRATION=1 to clone and run the pinned public target.",
)
def test_pinned_todomvc_target_supports_seed_toggle_filter_and_cleanup(
    browser: playwright.sync_api.Browser,
    tmp_path: Path,
) -> None:
    manager = TargetManager()
    target = manager.materialize(TARGET_MANIFEST, tmp_path / "target")
    adapter = TodoMVCAdapter()

    with manager.process(target, timeout_seconds=30) as running:
        context = browser.new_context()
        page = context.new_page()
        page.goto(running.base_url, wait_until="domcontentloaded")
        adapter.seed(
            page,
            [
                TodoItem(id=101, title="Active item", completed=False),
                TodoItem(id=102, title="Completed item", completed=True),
            ],
        )

        playwright.sync_api.expect(page.locator(".todo-list li")).to_have_count(2)
        playwright.sync_api.expect(page.locator(".todo-count")).to_contain_text(
            "1 item left"
        )

        page.get_by_role("link", name="Active").click()
        playwright.sync_api.expect(page.locator(".todo-list li")).to_have_count(1)
        playwright.sync_api.expect(page.locator(".todo-list label")).to_have_text(
            "Active item"
        )

        page.get_by_role("link", name="All").click()
        page.locator(".todo-list li", has_text="Active item").locator(".toggle").check()
        state = adapter.read(page)
        assert all(item.completed for item in state.items)

        page.get_by_role("button", name="Clear completed").click()
        playwright.sync_api.expect(page.locator(".todo-list li")).to_have_count(0)
        assert adapter.read(page).items == []
        context.close()
