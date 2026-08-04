from __future__ import annotations

from pathlib import import Path

import pytest

from test_workflow.config import load_settings


def test_load_settings_resolves_environment_variable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TARGET_URL", "http://127.0.0.1:8080")
    config = tmp_path / "config.yaml"
    config.write_text(
        "environment: test\nbase_url: ${TARGET_URL}\nallow_write: false\n",
        encoding="utf-8",
    )

    settings = load_settings(config)

    assert str(settings.base_url) == "http://127.0.0.1:8080/"
    assert settings.allow_write is False


def test_load_settings_rejects_unknown_browser(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text(
        "environment: test\nbase_url: http://localhost:8000\nbrowsers: [netscape]\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported browsers"):
        load_settings(config)
