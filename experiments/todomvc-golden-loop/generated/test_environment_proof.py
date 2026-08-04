from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from test_workflow.control_plane import build_runtime
from test_workflow.serialization import load_model
from test_workflow.specs import EnvironmentSpec, MockPlan
from test_workflow.virtual_service import create_virtual_service, load_behavior


def bundle_root() -> Path:
    return Path(os.environ["TEST_WORKFLOW_BUNDLE_ROOT"])


def test_seeded_browser_world_is_reproducible() -> None:
    runtime = build_runtime(bundle_root())
    storage = json.loads(runtime.storage_state_path.read_text())
    local_storage = storage["origins"][0]["localStorage"]
    todos_entry = next(item for item in local_storage if item["name"] == "todos-vanilla-es6")
    todos = json.loads(todos_entry["value"])

    assert [todo["id"] for todo in todos] == [1001, 1002]
    assert todos[0]["completed"] is False
    assert todos[1]["completed"] is True
    init_script = runtime.init_script_path.read_text()
    assert "2026-08-04T20:00:00+08:00" in init_script
    assert "20260804" in init_script


def test_virtual_dependency_is_contract_backed_and_observable() -> None:
    root = bundle_root()
    environment = load_model(root / "environment/environment-spec.yaml", EnvironmentSpec)
    plan = load_model(root / environment.mock_plan_path, MockPlan)
    telemetry = next(item for item in plan.dependencies if item.dependency == "telemetry_service")
    behavior = load_behavior(root / telemetry.behavior_path)
    client = TestClient(create_virtual_service(behavior))

    response = client.post("/track", json={"event": "todo.created"})

    assert response.status_code == 202
    assert response.json() == {
        "accepted": True,
        "event_id": "evt-deterministic-001",
    }
    calls = client.get("/__mock__/calls").json()
    assert calls[0]["route_id"] == "track-event"
