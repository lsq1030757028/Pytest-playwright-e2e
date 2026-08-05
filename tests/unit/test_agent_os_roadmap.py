from pathlib import Path

import yaml

ROADMAP_PATH = Path("docs/agent-os-roadmap.yaml")


def load_roadmap() -> dict[str, object]:
    return yaml.safe_load(ROADMAP_PATH.read_text(encoding="utf-8"))


def test_current_state_is_foundation_not_stage_delivery() -> None:
    roadmap = load_roadmap()

    assert roadmap["current_state"] == "FOUNDATION_BASELINE"
    assert roadmap["stage_delivery_status"] == "NOT_READY"
    assert roadmap["next_milestone"] == "M1"
    assert roadmap["active_module"] == "M1B_STORE_AND_PROGRESSIVE_RETRIEVAL_SPEC"
    assert roadmap["active_phase"] == "SPEC_NEXT"


def test_first_stage_delivery_requires_memory_model_and_project_gates() -> None:
    roadmap = load_roadmap()
    delivery_gate = roadmap["stage_delivery_gate"]

    assert delivery_gate["required_milestones"] == ["M1", "M2", "M3"]
    assert delivery_gate["safety_requirements"]["critical_false_green"] == 0
    assert (
        delivery_gate["safety_requirements"][
            "unauthorized_oracle_policy_permission_changes"
        ]
        == 0
    )
    assert (
        delivery_gate["safety_requirements"][
            "replayable_critical_evidence_percent"
        ]
        == 100
    )
    assert delivery_gate["safety_requirements"]["out_of_mandate_actions"] == 0


def test_milestone_order_and_statuses_are_unambiguous() -> None:
    roadmap = load_roadmap()
    milestones = roadmap["milestones"]
    ids = [milestone["id"] for milestone in milestones]
    statuses = {milestone["id"]: milestone["status"] for milestone in milestones}

    assert ids == ["M0", "M1", "M2", "M3", "M4", "M5", "M6"]
    assert len(ids) == len(set(ids))
    assert statuses == {
        "M0": "MERGED",
        "M1": "IN_PROGRESS",
        "M2": "PLANNED",
        "M3": "PLANNED",
        "M4": "PLANNED_AFTER_STAGE_GATE",
        "M5": "FUTURE",
        "M6": "FUTURE",
    }


def test_m1_tracks_closed_runtime_and_next_m1b_spec_truthfully() -> None:
    roadmap = load_roadmap()
    m1 = next(item for item in roadmap["milestones"] if item["id"] == "M1")

    assert m1["active_module"] == "M1B_STORE_AND_PROGRESSIVE_RETRIEVAL_SPEC"
    assert m1["module_status"]["M1.0"] == "MERGED_CLOSED"
    assert m1["module_status"]["M1A"] == "SPEC_MERGED_CLOSED"
    assert m1["module_status"]["M1A_RUNTIME_CONTRACTS"] == "MERGED_CLOSED"
    assert m1["module_status"]["M1B"] == "SPEC_NEXT"
    runtime = m1["completed_evidence"]["M1A_RUNTIME_CONTRACTS"]
    assert runtime["goal_issue"] == 43
    assert runtime["pull_request"] == 44
    assert runtime["merge_commit"] == "0585e357aebda650ee50ee95ff962b3ac81f6d4c"
    assert runtime["main_runtime_gate_run"] == 31018460853
    assert runtime["main_quality_run"] == 31018460602
    assert runtime["release_run"] == 31018460644
    assert runtime["critical_false_green"] == 0
    assert runtime["review_threads"] == 0
    assert runtime["implementation_branch_deleted"] is True
    assert m1["active_execution"]["phase"] == "SPEC"
    assert m1["active_execution"]["implementation_blocked_until_spec_approved"] is True
    assert m1["active_execution"]["production_backend_selected"] is False
    assert roadmap["next_execution_sequence"][0] == (
        "M1B_STORE_AND_PROGRESSIVE_RETRIEVAL_SPEC"
    )
    assert m1["gates"]["status"] == "OPEN"


def test_project_generalization_matrix_is_not_web_only() -> None:
    roadmap = load_roadmap()
    m3 = next(item for item in roadmap["milestones"] if item["id"] == "M3")
    matrix = m3["minimum_project_matrix"]

    assert matrix == {
        "complex_web": 2,
        "mobile": 2,
        "mini_program": 1,
        "embedded_iot": 1,
        "total": 6,
    }
    assert sum(value for key, value in matrix.items() if key != "total") == matrix["total"]
    assert m3["minimum_real_devices"]["android"] >= 1
    assert m3["minimum_real_devices"]["embedded_board"] >= 1
