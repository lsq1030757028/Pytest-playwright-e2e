from __future__ import annotations

import json
from collections.abc import Iterable

from playwright.sync_api import Page
from pydantic import BaseModel, Field, model_validator


class TodoItem(BaseModel):
    id: int
    title: str = Field(min_length=1)
    completed: bool = False


class TodoState(BaseModel):
    items: list[TodoItem]

    @model_validator(mode="after")
    def validate_unique_ids(self) -> TodoState:
        ids = [item.id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("TodoMVC seed contains duplicate item ids")
        return self


class TodoMVCAdapter:
    def __init__(self, storage_key: str = "todos-vanilla-es6") -> None:
        self.storage_key = storage_key

    def encode(self, items: Iterable[TodoItem | dict[str, object]]) -> str:
        state = TodoState(items=[TodoItem.model_validate(item) for item in items])
        payload = [item.model_dump(mode="json") for item in state.items]
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    def decode(self, raw_value: str | None) -> TodoState:
        if raw_value in {None, ""}:
            return TodoState(items=[])
        try:
            payload = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise ValueError("TodoMVC localStorage contains invalid JSON") from exc
        if not isinstance(payload, list):
            raise ValueError("TodoMVC localStorage payload must be a list")
        return TodoState(items=[TodoItem.model_validate(item) for item in payload])

    def seed(self, page: Page, items: Iterable[TodoItem | dict[str, object]]) -> None:
        encoded = self.encode(items)
        page.evaluate(
            "([key, value]) => window.localStorage.setItem(key, value)",
            [self.storage_key, encoded],
        )
        page.reload(wait_until="domcontentloaded")

    def read(self, page: Page) -> TodoState:
        raw_value = page.evaluate(
            "key => window.localStorage.getItem(key)",
            self.storage_key,
        )
        return self.decode(raw_value)

    def clear(self, page: Page) -> None:
        page.evaluate("key => window.localStorage.removeItem(key)", self.storage_key)
        page.reload(wait_until="domcontentloaded")
