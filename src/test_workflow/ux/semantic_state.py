from __future__ import annotations

from typing import Any

from ..adapters.todomvc import TodoMVCAdapter


def focus_snapshot(page: Any) -> dict[str, Any]:
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


def semantic_snapshot(page: Any) -> dict[str, Any]:
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
        "active_element": focus_snapshot(page),
    }


def normalized_todo_state(page: Any, adapter: TodoMVCAdapter) -> dict[str, Any]:
    """Return replay-stable user-visible state without generated IDs or transient focus."""
    state = adapter.read(page)
    active_count = sum(not item.completed for item in state.items)
    completed_count = sum(item.completed for item in state.items)
    storage = {
        "items": [
            {
                "title": item.title,
                "completed": item.completed,
            }
            for item in state.items
        ],
        "active_count": active_count,
        "completed_count": completed_count,
    }
    return {
        "storage": storage,
        "visible_labels": page.locator(".todo-list li:visible label").all_text_contents(),
        "remaining_count": (
            page.locator(".todo-count").inner_text()
            if page.locator(".todo-count").count()
            else ""
        ),
        "route": page.url.split("#", maxsplit=1)[1] if "#" in page.url else "",
    }


def safe_normalized_todo_state(page: Any, adapter: TodoMVCAdapter) -> dict[str, Any]:
    try:
        return normalized_todo_state(page, adapter)
    except Exception as exc:
        return {"state_unavailable": f"{type(exc).__name__}:{exc}"}
