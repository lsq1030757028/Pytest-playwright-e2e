from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from test_workflow.integrity import sha256_file
from test_workflow.proof import (
    MutationProofPlan,
    MutationProofReport,
    MutationResult,
    ProofExecution,
    TextMutation,
    TextMutationSpec,
    normalize_test_command,
    render_proof_markdown,
)


def mutation_spec(**overrides: object) -> TextMutationSpec:
    payload: dict[str, object] = {
        "id": "change-rule",
        "description": "change one business rule",
        "target_path": "dist/bundle.js",
        "find": "before",
        "replace": "after",
        "critical": True,
    }
    payload.update(overrides)
    return TextMutationSpec.model_validate(payload)


def execution(phase: str, return_code: int, mutation_id: str | None = None) -> ProofExecution:
    return ProofExecution(
        phase=phase,
        attempt=1,
        mutation_id=mutation_id,
        return_code=return_code,
        duration_seconds=0.1,
        stdout_path="stdout.log",
        stderr_path="stderr.log",
        junit_path="junit.xml",
    )


def test_text_mutation_applies_once_and_restores_exact_content(tmp_path: Path) -> None:
    app_dir = tmp_path / "app"
    target = app_dir / "dist" / "bundle.js"
    target.parent.mkdir(parents=True)
    target.write_text("prefix before suffix", encoding="utf-8")
    original_hash = sha256_file(target)
    patch = TextMutation(app_dir, mutation_spec())

    with patch as applied:
        assert target.read_text(encoding="utf-8") == "prefix after suffix"
        assert applied.original_sha256 == original_hash
        assert applied.mutated_sha256 != original_hash

    assert target.read_text(encoding="utf-8") == "prefix before suffix"
    assert patch.restored_sha256() == original_hash


def test_text_mutation_rejects_missing_or_ambiguous_match(tmp_path: Path) -> None:
    app_dir = tmp_path / "app"
    target = app_dir / "dist" / "bundle.js"
    target.parent.mkdir(parents=True)
    target.write_text("no match", encoding="utf-8")

    with pytest.raises(ValueError, match="found 0"), TextMutation(
        app_dir, mutation_spec()
    ):
        pass

    target.write_text("before and before", encoding="utf-8")
    with pytest.raises(ValueError, match="found 2"), TextMutation(
        app_dir, mutation_spec()
    ):
        pass


def test_mutation_spec_rejects_path_traversal_and_noop() -> None:
    with pytest.raises(ValidationError, match="inside the target checkout"):
        mutation_spec(target_path="../bundle.js")
    with pytest.raises(ValidationError, match="must change"):
        mutation_spec(replace="before")


def test_proof_plan_requires_unique_mutation_ids() -> None:
    duplicate = mutation_spec().model_dump()
    with pytest.raises(ValidationError, match="mutation ids must be unique"):
        MutationProofPlan.model_validate(
            {
                "id": "proof",
                "target_manifest": "target.yaml",
                "test_command": ["python", "-m", "pytest"],
                "mutations": [duplicate, duplicate],
            }
        )


def test_report_markdown_surfaces_false_green() -> None:
    passed_execution = execution("mutation", 1, "killed")
    survived_execution = execution("mutation", 0, "survived")
    report = MutationProofReport(
        plan_id="proof",
        target_revision="abc1234",
        status="failed",
        baseline=[execution("baseline", 0)],
        mutations=[
            MutationResult(
                mutation_id="killed",
                description="killed",
                critical=True,
                killed=True,
                original_sha256="a",
                mutated_sha256="b",
                restored_sha256="a",
                execution=passed_execution,
            ),
            MutationResult(
                mutation_id="survived",
                description="survived",
                critical=True,
                killed=False,
                original_sha256="a",
                mutated_sha256="c",
                restored_sha256="a",
                execution=survived_execution,
            ),
        ],
        restored=[execution("restored", 0)],
        mutation_score=0.5,
        critical_false_green=1,
        evidence_dir="evidence",
    )

    markdown = render_proof_markdown(report)

    assert "50%" in markdown
    assert "Critical false green: `1`" in markdown
    assert "SURVIVED" in markdown


def test_python_command_uses_current_interpreter() -> None:
    normalized = normalize_test_command(["python", "-m", "pytest"])
    assert normalized[0] != "python"
    assert normalized[1:] == ["-m", "pytest"]
