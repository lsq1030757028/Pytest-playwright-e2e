from __future__ import annotations

from pathlib import Path

from test_workflow.harness import (
    CapabilityRef,
    CapabilityRegistry,
    CapabilityRequest,
    CapabilityResultStatus,
    ExecutionBudget,
    InMemoryArtifactStore,
    MutationProofCapability,
    PytestRunCapability,
    SpecValidateCapability,
    StoreExecutionContext,
    TargetManifestValidateCapability,
    register_existing_capabilities,
)
from test_workflow.proof import MutationProofReport

REPO_ROOT = Path(__file__).resolve().parents[2]


def source(
    store: InMemoryArtifactStore,
    *,
    artifact_id: str,
    artifact_type: str,
    path: str,
):
    return store.put(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        schema_version=1,
        content={"path": path},
        created_by=CapabilityRef(name="source.register", version="1.0.0"),
    )


def request(name: str, request_id: str, input_artifacts=(), **kwargs) -> CapabilityRequest:
    return CapabilityRequest(
        request_id=request_id,
        capability=CapabilityRef(name=name, version="1.0.0"),
        input_artifacts=tuple(input_artifacts),
        **kwargs,
    )


def test_spec_validate_capability_wraps_existing_testspec_loader() -> None:
    store = InMemoryArtifactStore()
    ref = source(
        store,
        artifact_id="sources/spec/todo/v1",
        artifact_type="SpecSource",
        path="experiments/todomvc-golden-loop/spec/test-spec.yaml",
    )
    result = SpecValidateCapability(REPO_ROOT).execute(
        request("spec.validate", "adapter-spec", (ref,)),
        StoreExecutionContext(store),
    )

    content = store.get(result.artifacts[0]).content
    assert result.status == CapabilityResultStatus.SUCCESS
    assert content["valid"] is True
    assert content["spec_id"]
    assert content["case_count"] >= 1
    assert content["oracle_count"] >= 1


def test_target_validate_capability_wraps_manifest_loader() -> None:
    store = InMemoryArtifactStore()
    ref = source(
        store,
        artifact_id="sources/target/todo/v1",
        artifact_type="TargetSource",
        path="targets/percy-example-todomvc/target.yaml",
    )
    result = TargetManifestValidateCapability(REPO_ROOT).execute(
        request("target.validate", "adapter-target", (ref,)),
        StoreExecutionContext(store),
    )

    content = store.get(result.artifacts[0]).content
    assert result.status == CapabilityResultStatus.SUCCESS
    assert content["target_id"] == "percy-example-todomvc"
    assert len(content["revision"]) == 40


def test_pytest_run_capability_executes_only_selected_test_asset() -> None:
    store = InMemoryArtifactStore()
    result = PytestRunCapability(REPO_ROOT).execute(
        request(
            "test.run",
            "adapter-test-run",
            budget=ExecutionBudget(subprocesses=1, wall_time_seconds=60),
            parameters={
                "tests": ["tests/assets/harness/3.0e/test_selected_harness.py"],
                "pytest_args": ["-q"],
            },
        ),
        StoreExecutionContext(store),
    )

    content = store.get(result.artifacts[0]).content
    assert result.status == CapabilityResultStatus.SUCCESS
    assert content["return_code"] == 0
    assert "1 passed" in content["stdout"]
    assert result.metrics.subprocesses == 1


def test_pytest_run_rejects_paths_outside_tests() -> None:
    result = PytestRunCapability(REPO_ROOT).execute(
        request(
            "test.run",
            "adapter-path-reject",
            budget=ExecutionBudget(subprocesses=1, wall_time_seconds=60),
            parameters={"tests": ["pyproject.toml"]},
        ),
        StoreExecutionContext(InMemoryArtifactStore()),
    )
    assert result.status == CapabilityResultStatus.FAILED
    assert "inside tests" in result.error


class FakeProofRunner:
    def run(self, plan, *, workspace, evidence_dir) -> MutationProofReport:
        return MutationProofReport(
            plan_id="fake-proof",
            target_revision="a" * 40,
            status="passed",
            baseline=[],
            mutations=[],
            restored=[],
            mutation_score=1,
            critical_false_green=0,
            evidence_dir=str(evidence_dir),
        )


def test_mutation_proof_capability_persists_report_from_runner() -> None:
    store = InMemoryArtifactStore()
    ref = source(
        store,
        artifact_id="sources/proof/todo/v1",
        artifact_type="ProofSource",
        path="proofs/todomvc/plan.yaml",
    )
    result = MutationProofCapability(REPO_ROOT, runner=FakeProofRunner()).execute(
        request(
            "proof.run",
            "adapter-proof",
            (ref,),
            budget=ExecutionBudget(api_calls=1, subprocesses=1, wall_time_seconds=1800),
        ),
        StoreExecutionContext(store),
    )

    assert result.status == CapabilityResultStatus.SUCCESS
    assert store.get(result.artifacts[0]).content["plan_id"] == "fake-proof"


def test_register_existing_capabilities_is_complete() -> None:
    registry = CapabilityRegistry()
    register_existing_capabilities(registry, REPO_ROOT)
    assert [item.name for item in registry.list_descriptors()] == [
        "proof.run",
        "spec.validate",
        "target.validate",
        "test.run",
    ]
