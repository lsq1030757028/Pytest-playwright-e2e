from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, HttpUrl, field_validator

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


class TestSettings(BaseModel):
    environment: str = "local"
    base_url: HttpUrl
    health_path: str = "/health"
    allow_write: bool = False
    browsers: list[str] = Field(default_factory=lambda: ["chromium"])
    artifacts_dir: Path = Path("test-results")
    request_timeout_seconds: float = 10

    @field_validator("health_path")
    @classmethod
    def health_path_must_be_absolute(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("health_path must start with '/'")
        return value

    @field_validator("browsers")
    @classmethod
    def validate_browsers(cls, value: list[str]) -> list[str]:
        allowed = {"chromium", "firefox", "webkit"}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unsupported browsers: {sorted(unknown)}")
        return value

    @property
    def health_url(self) -> str:
        return f"{str(self.base_url).rstrip('/')}{self.health_path}"


def _resolve_env(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _resolve_env(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_env(item) for item in value]
    if not isinstance(value, str):
        return value

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in os.environ:
            raise ValueError(f"missing environment variable: {name}")
        return os.environ[name]

    return _ENV_PATTERN.sub(replace, value)


def load_settings(path: str | Path) -> TestSettings:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"config file does not exist: {config_path}")

    with config_path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}

    return TestSettings.model_validate(_resolve_env(raw))
