from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


def load_document(path: str | Path) -> object:
    document_path = Path(path)
    text = document_path.read_text(encoding="utf-8")
    if document_path.suffix.lower() == ".json":
        return json.loads(text)
    return yaml.safe_load(text)


def load_model(path: str | Path, model: type[ModelT]) -> ModelT:
    return model.model_validate(load_document(path))


def dump_model(path: str | Path, value: BaseModel) -> None:
    document_path = Path(path)
    document_path.parent.mkdir(parents=True, exist_ok=True)
    payload = value.model_dump(mode="json", exclude_none=True)
    if document_path.suffix.lower() == ".json":
        document_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return
    document_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
