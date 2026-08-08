from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC_MD = ROOT / "docs/specs/test-agent-runtime-beta.md"
SPEC_YAML = ROOT / "docs/specs/test-agent-runtime-beta.yaml"
THREAT_MD = ROOT / "docs/security/test-agent-runtime-beta-threat-model.md"
TEST_DESIGN_MD = ROOT / "docs/testing/test-agent-runtime-beta-test-design.md"
ROADMAP_YAML = ROOT / "docs/test-agent-runtime-beta-roadmap.yaml"
WORKFLOW = ROOT / ".github/workflows/test-agent-runtime-beta-spec.yml"


def load_yaml(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_spec_identity_authority_and_phase_are_truthful() -> None:
    spec = load_yaml(SPEC_YAML)
    markdown = SPEC_MD.read_text(encoding="utf-8")

    assert spec["spec_id"] == "SPEC-TEST-AGENT-RUNTIME-BETA"
    assert spec["version"] == "0.1.0"
    assert spec["status"] == "CANDIDATE"
    assert spec["goal_issue"] == 66
    assert spec["parent_campaign_issue"] == 65
    assert spec["work_item_id"] == "TEST-AGENT-RUNTIME-BETA-ARCHITECTURE-SPEC"
    assert spec["authority"]["m1_m3_mandate_extended"] is False
    assert spec["product"]["lifecycle_claim"] == "SPEC_ONLY"
    assert "It does not implement the runtime" in markdown
    assert (
        "Runtime implementation may begin only after this SPEC is approved and merged"
        in markdown
    )


def test_beta_journey_has_a_real_entrypoint_and_full_loop() -> None:
    spec = load_yaml(SPEC_YAML)
    commands = spec["entrypoint"]["commands"]
    markdown = SPEC_MD.read_text(encoding="utf-8")

    assert set(commands) == {"submit", "status", "result", "cancel", "events"}
    assert commands["submit"] == "test-agent job submit"
    for phrase in (
        "builds a governed test plan",
        "generates or updates reviewable Pytest + Playwright tests",
        "executes them in a reproducible cloud runtime",
        "performs bounded test-workflow diagnosis and repair",
        "survives a process restart",
    ):
        assert phrase in markdown


def test_job_lifecycle_concurrency_and_verdicts_fail_closed() -> None:
    spec = load_yaml(SPEC_YAML)
    lifecycle = spec["job_lifecycle"]
    states = lifecycle["states"]
    terminals = lifecycle["terminal_states"]
    verdicts = set(spec["verdicts"])

    assert len(states) == len(set(states))
    assert set(terminals) <= set(states)
    assert lifecycle["concurrency"] == {
        "append_only_events": True,
        "expected_revision_required": True,
        "stale_write_result": "EXPLICIT_CONFLICT",
        "duplicate_delivery": "IDEMPOTENT",
    }
    assert {
        "VERIFIED_SUCCESS",
        "PRODUCT_DEFECT",
        "TEST_DEFECT",
        "ENVIRONMENT_FAILURE",
        "INSUFFICIENT_EVIDENCE",
        "ORACLE_CONFLICT",
        "POLICY_BLOCKED",
        "CANCELLED",
        "TIMED_OUT",
    } == verdicts
    assert spec["success_authority"] == "DETERMINISTIC_VERIFIER"
    assert spec["model_output_authority"] == "CANDIDATE_ONLY"


def test_durable_runtime_distinguishes_job_state_from_governed_memory() -> None:
    spec = load_yaml(SPEC_YAML)
    durable = spec["durable_runtime"]

    assert durable["beta_job_store"] == {
        "backend": "SQLITE_WAL",
        "persistent_volume_required": True,
        "purpose": "JOB_STATE_NOT_GOVERNED_MEMORY",
    }
    assert durable["artifact_store"]["backend"] == "CONTENT_ADDRESSED_FILESYSTEM"
    assert durable["artifact_store"]["hash"] == "SHA256"
    assert durable["startup_recovery"]["duplicate_uncertain_side_effect_forbidden"] is True
    assert spec["memory"]["memory_may_override_oracle_policy_permission"] is False


def test_workspace_generation_and_repair_cannot_modify_product_source() -> None:
    spec = load_yaml(SPEC_YAML)

    assert spec["workspace"]["base_project_agent_read_only"] is True
    assert spec["workspace"]["product_source_write_allowed"] is False
    assert spec["workspace"]["model_shell_interpolation_allowed"] is False
    assert spec["workspace"]["network_default"] == "DENY"
    assert spec["test_generation"]["fixed_sleep_allowed"] is False
    assert spec["test_generation"]["blind_retry_allowed"] is False
    assert spec["test_generation"]["initial_product_source_repair_allowed"] is False
    assert spec["diagnosis_repair"]["product_defect_repair_action"] == "STOP_AND_REPORT"
    assert spec["diagnosis_repair"]["maximum_repair_cycles"] == 2


def test_required_evidence_and_execution_pins_are_complete() -> None:
    spec = load_yaml(SPEC_YAML)

    assert {
        "base_commit",
        "test_patch_hash",
        "project_adapter_version",
        "dependency_lock_revision",
        "pytest_version",
        "playwright_browser_revision",
        "environment_image",
        "selected_test_nodes",
        "seed",
        "timeouts",
        "evidence_profile",
        "worker_identity_and_lease",
    } == set(spec["execution_manifest"]["required_pins"])
    assert {
        "job_plan_attempt_run_manifests",
        "project_and_patch_hashes",
        "command_manifest",
        "redacted_stdout_stderr",
        "junit",
        "environment_manifest",
        "deterministic_verifier_output",
        "artifact_index_and_hashes",
        "reset_cleanup_result",
        "replay_instructions",
    } <= set(spec["evidence_bundle"]["required"])


def test_budgets_are_finite_and_safety_thresholds_are_zero() -> None:
    spec = load_yaml(SPEC_YAML)
    budgets = spec["budgets"]
    invariants = spec["protected_invariants"]

    assert all(isinstance(value, int) and value > 0 for value in budgets.values())
    assert budgets["repair_cycles"] == 2
    assert budgets["execution_attempts"] == 3
    assert budgets["concurrent_workers_per_job"] == 1
    assert budgets["wall_clock_job_minutes"] == 45
    assert set(invariants.values()) == {0}


def test_vertical_slices_form_a_dependency_closed_operating_path() -> None:
    spec = load_yaml(SPEC_YAML)
    roadmap = load_yaml(ROADMAP_YAML)
    slices = spec["vertical_slices"]
    ids = [item["id"] for item in slices]

    assert ids == ["BETA-A", "BETA-B", "BETA-C", "BETA-D", "BETA-E"]
    known: set[str] = set()
    for item in slices:
        assert set(item["depends_on"]) <= known
        assert item["operational_result"]
        assert item["proves"]
        known.add(item["id"])
    assert roadmap["delivery_principle"] == (
        "VERTICAL_OPERATING_SLICE_BEFORE_UNUSED_HORIZONTAL_SUBSYSTEM"
    )
    assert [item["id"] for item in roadmap["slices"]] == ids
    assert roadmap["slices"][0]["state"] == "PLANNED"
    assert all(item["state"] == "BLOCKED" for item in roadmap["slices"][1:])


def test_m1_to_m6_are_exercised_by_product_slices_not_declared_complete() -> None:
    spec = load_yaml(SPEC_YAML)
    roadmap = load_yaml(ROADMAP_YAML)

    assert set(spec["milestone_mapping"]) == {"M1", "M2", "M3", "M4", "M5", "M6"}
    assert set(roadmap["milestone_to_slice"]) == {"M1", "M2", "M3", "M4", "M5", "M6"}
    assert roadmap["product_state"] == "SPEC_ONLY_NOT_OPERATIONAL"
    assert spec["implementation_gate"] == {
        "runtime_may_begin_after_spec_merge": True,
        "first_goal_must_deliver": "BETA-A",
        "unused_horizontal_subsystem_first": False,
    }


def test_threat_model_and_test_design_cover_beta_specific_failure_modes() -> None:
    threat = THREAT_MD.read_text(encoding="utf-8")
    design = TEST_DESIGN_MD.read_text(encoding="utf-8")

    threat_ids = {f"BETA-T{index:02d}" for index in range(1, 36)}
    assert all(threat_id in threat for threat_id in threat_ids)
    for phrase in (
        "Repository prompt injection",
        "False-success repair",
        "Restart during browser action",
        "Evidence substitution",
        "Cost exhaustion",
    ):
        assert phrase in threat
    for slice_id in ("Slice A", "Slice B", "Slice C", "Slice D", "Slice E"):
        assert slice_id in design
    assert "Human UAT is authoritative" in design


def test_workflow_is_read_only_and_runs_dedicated_validation() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "permissions:\n  contents: read" in workflow
    assert "pull_request_target" not in workflow
    assert "tests/unit/test_test_agent_runtime_beta_spec.py" in workflow
    assert "uv run pytest" in workflow
    assert "uv run ruff check" in workflow
