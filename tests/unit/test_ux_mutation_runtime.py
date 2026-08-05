from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from test_workflow.integrity import sha256_bytes
from test_workflow.targets import MaterializedTarget, TargetManifest
from test_workflow.ux_mutation import (
    MutationFamily,
    ProofState,
    TargetMutationSandbox,
    UXMutation,
    UXMutationProofRunner,
    load_ux_mutation_proof,
)
from test_workflow.ux_mutation.models import RequiredUnmodifiedFile
from test_workflow.ux_mutation.runner import _TransitionRecorder

ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN = ROOT / "benchmarks/ux/ux1/campaign.yaml"
CODE_SHA = "a" * 40


def _run_git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _sha256(value: bytes) -> str:
    return f"sha256:{sha256_bytes(value)}"


def _mutation(path: str = "index.html") -> UXMutation:
    original = b"<html>\nMARKER\n</html>\n"
    search = "MARKER"
    replacement = "MUTATED"
    postimage = original.decode().replace(search, replacement, 1).encode()
    return UXMutation(
        mutation_id="UXM-001",
        family=MutationFamily.MISSING_FEEDBACK,
        title="test exact bounded mutation",
        target_path=path,
        preimage_sha256=_sha256(original),
        search_text=search,
        search_sha256=_sha256(search.encode()),
        replacement_text=replacement,
        replacement_sha256=_sha256(replacement.encode()),
        expected_replacement_count=1,
        postimage_sha256=_sha256(postimage),
        affected_journey_refs=("novice-add-task@1.0.0",),
        oracle_refs=("UX-ORACLE-ADD-TASK@1.0.0",),
        expected_failed_checkpoints=("task_is_visible_after_submit",),
        expected_failure_classification="DETERMINISTIC_FEEDBACK_FAILURE",
        minimum_evidence_level="E3",
        disallowed_kill_basis="AI_CANDIDATE_ONLY",
    )


def _target(tmp_path: Path) -> tuple[MaterializedTarget, str, str]:
    root = tmp_path / "target"
    root.mkdir()
    _run_git(root, "init")
    _run_git(root, "config", "user.email", "test@example.invalid")
    _run_git(root, "config", "user.name", "UX Mutation Test")
    (root / "index.html").write_bytes(b"<html>\nMARKER\n</html>\n")
    (root / "dist").mkdir()
    (root / "dist/bundle.js").write_text("console.log('stable');\n", encoding="utf-8")
    _run_git(root, "add", ".")
    _run_git(root, "commit", "-m", "fixture")
    revision = _run_git(root, "rev-parse", "HEAD")
    mutable_blob = _run_git(root, "rev-parse", "HEAD:index.html")
    required_blob = _run_git(root, "rev-parse", "HEAD:dist/bundle.js")
    manifest = TargetManifest(
        id="local-todomvc-fixture",
        repository="local",
        revision=revision,
        start_command=["python", "-m", "http.server", "${PORT}"],
    )
    return MaterializedTarget(manifest, root, root, revision), mutable_blob, required_blob


def test_ux1_campaign_loads_five_pinned_mutations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UX_CODE_SHA", CODE_SHA)
    loaded = load_ux_mutation_proof(CAMPAIGN)

    assert loaded.plan.mode == "SHADOW"
    assert loaded.plan.release_effect == "NONBLOCKING_SHADOW"
    assert loaded.plan.human_uat_required is True
    assert [item.mutation_id for item in loaded.selected_mutations] == [
        "UXM-001",
        "UXM-002",
        "UXM-003",
        "UXM-004",
        "UXM-005",
    ]
    assert (
        loaded.mutation_catalog.target.revision
        == loaded.ux_campaign.plan.pins.target_revision
    )
    assert all(
        item.mutable_git_blob_sha1
        == loaded.mutation_catalog.target.mutable_file.git_blob_sha1
        for item in loaded.selected_mutations
    )
    assert all(
        item.required_unmodified_files
        == loaded.mutation_catalog.target.required_unmodified_files
        for item in loaded.selected_mutations
    )


def test_sandbox_applies_and_restores_exact_bytes(tmp_path: Path) -> None:
    target, mutable_blob, required_blob = _target(tmp_path)
    sandbox = TargetMutationSandbox(
        target,
        _mutation(),
        expected_mutable_blob_sha1=mutable_blob,
        required_unmodified_files=(
            RequiredUnmodifiedFile(
                path="dist/bundle.js",
                git_blob_sha1=required_blob,
            ),
        ),
    )

    applied = sandbox.apply()
    assert applied.changed_files == ("index.html",)
    assert target.app_dir.joinpath("index.html").read_text(encoding="utf-8") == (
        "<html>\nMUTATED\n</html>\n"
    )

    restored = sandbox.restore()
    assert restored.restore_clean is True
    assert restored.restored_sha256 == sha256_bytes(b"<html>\nMARKER\n</html>\n")
    assert _run_git(target.checkout_dir, "status", "--porcelain") == ""


def test_sandbox_rejects_required_file_blob_drift(tmp_path: Path) -> None:
    target, mutable_blob, _ = _target(tmp_path)
    sandbox = TargetMutationSandbox(
        target,
        _mutation(),
        expected_mutable_blob_sha1=mutable_blob,
        required_unmodified_files=(
            RequiredUnmodifiedFile(
                path="dist/bundle.js",
                git_blob_sha1="0" * 40,
            ),
        ),
    )

    with pytest.raises(ValueError, match="required unmodified Git blob mismatch"):
        sandbox.verify_clean_preimage()


def test_sandbox_rejects_symbolic_link_target(tmp_path: Path) -> None:
    target, _, _ = _target(tmp_path)
    link = target.app_dir / "linked.html"
    try:
        link.symlink_to(target.app_dir / "index.html")
    except OSError:
        pytest.skip("symbolic links are unavailable on this platform")

    with pytest.raises(ValueError, match="symbolic link"):
        TargetMutationSandbox(target, _mutation("linked.html"))


def test_workspace_must_be_outside_repository(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="isolated from the repository"):
        UXMutationProofRunner._prepare_workspace(ROOT / ".target-work/ux1", ROOT)

    workspace = tmp_path / "isolated-workspace"
    UXMutationProofRunner._prepare_workspace(workspace, ROOT)
    assert workspace.is_dir()


def test_survived_mutation_restores_before_terminal_state() -> None:
    recorder = _TransitionRecorder("UXM-001")
    recorder.move(ProofState.BASELINE_RUNNING, "baseline_started")
    recorder.move(ProofState.BASELINE_PROVEN, "baseline_passed")
    recorder.move(ProofState.MUTATION_APPLYING, "patch_started")
    recorder.move(ProofState.MUTATION_VERIFIED, "postimage_verified")
    recorder.move(ProofState.MUTATED_RUNNING, "mutated_started")
    recorder.move(ProofState.RESTORING, "survived_restore_started")
    recorder.move(ProofState.RESTORE_VERIFIED, "exact_restore_verified")
    recorder.move(ProofState.MUTATION_SURVIVED, "expected_failure_missing")

    assert recorder.current == ProofState.MUTATION_SURVIVED
    assert recorder.events[-2].to_state == ProofState.RESTORE_VERIFIED


def test_illegal_state_transition_is_rejected() -> None:
    recorder = _TransitionRecorder("UXM-001")
    with pytest.raises(ValueError, match="illegal UX mutation proof transition"):
        recorder.move(ProofState.CLOSED_PASS, "invalid_shortcut")
