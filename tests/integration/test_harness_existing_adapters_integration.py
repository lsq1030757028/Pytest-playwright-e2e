from __future__ import annotations

from pathlib import Path

import pytest

from test_workflow.harness import (
    CapabilityRef,
    CapabilityRegistry,
    CapabilityRequest,
    ExecutionBudget,
    ExecutionNode,
    FileArtifactStore,
    Orchestrator,
    PermissionScope,
    PlanStatus,
    WorkflowCompiler,
    register_existing_capabilities,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def source(store: FileArtifactStore, artifact_id: str, artifact_type: str, path: str):
    return store.put(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        schema_version=1,
        content={"path": path},
        created_by=CapabilityRef(name="source.register", version="1.0.0"),
    )


@pytest.mark.harness_integration
def test_l1_todomvc_harness_gate_runs_only_minimal_capabilities(tmp_path: Path) -> None:
    store = FileArtifactStore(tmp_path / "artifacts")
    spec_source = source(
        store,
        "sources/spec/todo/v1",
        "SpecSource",
        "experiments/todomvc-golden-loop/spec/test-spec.yaml",
    )
    target_source = source(
        store,
        "sources/target/todo/v1",
        "TargetSource",
        "targets/percy-example-todomvc/target.yaml",
    )
    registry = CapabilityRegistry()
    register_existing_capabilities(registry, REPO_ROOT)

    plan = WorkflowCompiler(registry).compile(
        "l1-todomvc-golden",
        (
            ExecutionNode(
                node_id="spec",
                request=CapabilityRequest(
                    request_id="l1-spec",
                    capability=CapabilityRef(name="spec.validate", version="1.0.0"),
                    input_artifacts=(spec_source,),
                    budget=ExecutionBudget(wall_time_seconds=5),
                    permissions=PermissionScope(
                        read=frozenset({"artifacts/spec/*", "repository/specs/*"}),
                        write=frozenset({"artifacts/validation/*"}),
                    ),
                ),
            ),
            ExecutionNode(
                node_id="target",
                request=CapabilityRequest(
                    request_id="l1-target",
                    capability=CapabilityRef(name="target.validate", version="1.0.0"),
                    input_artifacts=(target_source,),
                    budget=ExecutionBudget(wall_time_seconds=5),
                    permissions=PermissionScope(
                        read=frozenset({"artifacts/target/*", "repository/targets/*"}),
                        write=frozenset({"artifacts/validation/*"}),
                    ),
                ),
            ),
            ExecutionNode(
                node_id="test",
                request=CapabilityRequest(
                    request_id="l1-selected-test",
                    capability=CapabilityRef(name="test.run", version="1.0.0"),
                    budget=ExecutionBudget(
                        subprocesses=1,
                        wall_time_seconds=120,
                        artifact_bytes=1_000_000,
                    ),
                    permissions=PermissionScope(
                        read=frozenset({"repository/tests/*"}),
                        write=frozenset({"artifacts/test-runs/*"}),
                        execute=frozenset({"pytest"}),
                        allow_subprocess=True,
                    ),
                    parameters={
                        "tests": ["tests/assets/harness/3.0e/test_selected_harness.py"],
                        "pytest_args": ["-q"],
                    },
                ),
                depends_on=("spec", "target"),
            ),
        ),
    )

    checkpoint = Orchestrator(registry, store).execute(plan)

    assert plan.parallel_batches() == (("spec", "target"), ("test",))
    assert checkpoint.status == PlanStatus.SUCCEEDED
    assert all(item.status == "succeeded" for item in checkpoint.nodes)
    assert registry.contains(CapabilityRef(name="proof.run", version="1.0.0"))
    assert all(item.node_id != "proof" for item in checkpoint.nodes)
    assert all(event.event_type == "policy.allowed" for event in checkpoint.events)
    assert store.get(checkpoint.node_map()["test"].result.artifacts[0]).content[
        "return_code"
    ] == 0
