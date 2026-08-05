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


def test_milestone_order_and_statuses_are_unambiguous() -> None:
    roadmap = load_roadmap()
    milestones = roadmap["milestones"]
    ids = [milestone["id"] for milestone in milestones]
    statuses = {milestone["id"]: milestone["status"] for milestone in milestones}

    assert ids == ["M0", "M1", "M2", "M3", "M4", "M5", "M6"]
    assert len(ids) == len(set(ids))
    assert statuses == {
        "M0": "MERGED",
        "M1": "NEXT",
        "M2": "PLANNED",
        "M3": "PLANNED",
        "M4": "PLANNED_AFTER_STAGE_GATE",
        "M5": "FUTURE",
        "M6": "FUTURE",
    }


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
