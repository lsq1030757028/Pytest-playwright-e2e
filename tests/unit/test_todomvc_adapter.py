from __future__ import annotations

import pytest

from test_workflow.adapters.todomvc import TodoItem, TodoMVCAdapter


def test_todomvc_adapter_round_trips_state() -> None:
    adapter = TodoMVCAdapter()
    encoded = adapter.encode(
        [
            TodoItem(id=1, title="Read requirement", completed=False),
            TodoItem(id=2, title="Run regression", completed=True),
        ]
    )

    state = adapter.decode(encoded)

    assert [item.title for item in state.items] == [
        "Read requirement",
        "Run regression",
    ]
    assert state.items[1].completed is True


def test_todomvc_adapter_rejects_duplicate_ids() -> None:
    adapter = TodoMVCAdapter()

    with pytest.raises(ValueError, match="duplicate"):
        adapter.encode(
            [
                {"id": 1, "title": "first", "completed": False},
                {"id": 1, "title": "second", "completed": False},
            ]
        )


def test_todomvc_adapter_rejects_corrupt_storage() -> None:
    adapter = TodoMVCAdapter()

    with pytest.raises(ValueError, match="invalid JSON"):
        adapter.decode("not-json")
