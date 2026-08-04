from __future__ import annotations

import os

import pytest
from playwright.sync_api import Page, expect

from test_workflow.adapters.todomvc import TodoItem, TodoMVCAdapter


def commit_new_todo(page: Page, title: str) -> None:
    new_todo = page.locator(".new-todo")
    new_todo.fill(title)
    new_todo.press("Enter")
    new_todo.blur()


@pytest.fixture
def todo_page(page: Page) -> Page:
    target_url = os.getenv("TODO_TARGET_URL")
    if not target_url:
        pytest.skip("TODO_TARGET_URL is required for TodoMVC business regression")
    page.goto(target_url, wait_until="domcontentloaded")
    TodoMVCAdapter().clear(page)
    return page


@pytest.mark.target_regression
def test_rejects_blank_items_and_trims_new_item_title(todo_page: Page) -> None:
    commit_new_todo(todo_page, "   ")
    expect(todo_page.locator(".todo-list li")).to_have_count(0)

    commit_new_todo(todo_page, "  Plan release  ")
    expect(todo_page.locator(".todo-list li")).to_have_count(1)
    expect(todo_page.locator(".todo-list label")).to_have_text("Plan release")
    assert TodoMVCAdapter().read(todo_page).items[0].title == "Plan release"


@pytest.mark.target_regression
def test_filters_and_remaining_counter_reflect_business_state(todo_page: Page) -> None:
    adapter = TodoMVCAdapter()
    adapter.seed(todo_page, [
        TodoItem(id=201, title="Active item", completed=False),
        TodoItem(id=202, title="Completed item", completed=True),
    ])
    expect(todo_page.locator(".todo-count")).to_contain_text("1 item left")
    todo_page.get_by_role("link", name="Active").click()
    expect(todo_page.locator(".todo-list label")).to_have_text("Active item")
    todo_page.get_by_role("link", name="Completed").click()
    expect(todo_page.locator(".todo-list label")).to_have_text("Completed item")


@pytest.mark.target_regression
def test_clear_completed_preserves_active_items(todo_page: Page) -> None:
    adapter = TodoMVCAdapter()
    adapter.seed(todo_page, [
        TodoItem(id=301, title="Keep active", completed=False),
        TodoItem(id=302, title="Remove completed", completed=True),
    ])
    todo_page.get_by_role("button", name="Clear completed").click()
    expect(todo_page.locator(".todo-list li")).to_have_count(1)
    expect(todo_page.locator(".todo-list label")).to_have_text("Keep active")
    state = adapter.read(todo_page)
    assert [item.title for item in state.items] == ["Keep active"]
    assert state.items[0].completed is False


@pytest.mark.target_regression
def test_new_item_persists_across_page_reload(todo_page: Page) -> None:
    commit_new_todo(todo_page, "Persist me")
    expect(todo_page.locator(".todo-list label")).to_have_text("Persist me")
    todo_page.reload(wait_until="domcontentloaded")
    expect(todo_page.locator(".todo-list li")).to_have_count(1)
    expect(todo_page.locator(".todo-list label")).to_have_text("Persist me")
    assert TodoMVCAdapter().read(todo_page).items[0].title == "Persist me"
