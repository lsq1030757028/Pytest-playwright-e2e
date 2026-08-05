from __future__ import annotations

import pytest
from pydantic import ValidationError

from test_workflow.specs import TestSpec as WorkflowTestSpec


BASE_SPEC = {
    "id": "TODO-001",
    "title": "Create a todo",
    "requirement_sources": [{"id": "REQ-1", "source": "rough requirement"}],
    "facts": [
        {
            "id": "F-1",
            "statement": "User can add todos",
            "source": "REQ-1",
            "confidence": "confirmed",
        }
    ],
    "assumptions": [],
    "risks": [],
    "truth_boundary": {
        "must_be_real": ["todo.create"],
        "may_be_mocked": ["system.clock"],
    },
    "cases": [
        {
            "id": "CASE-1",
            "title": "Add a valid todo",
            "risk": "high",
            "actions": [{"name": "add_todo", "params": {"title": "Buy milk"}}],
            "oracles": [
                {
                    "id": "O-1",
                    "source": "requirement",
                    "expression": "todo.title == 'Buy milk'",
                    "expected": True,
                    "basis_ref": "F-1",
                }
            ],
        }
    ],
}


def test_test_spec_accepts_traceable_oracle() -> None:
    spec = WorkflowTestSpec.model_validate(BASE_SPEC)
    assert spec.cases[0].oracles[0].basis_ref == "F-1"


def test_test_spec_rejects_unconfirmed_assumption_as_oracle() -> None:
    payload = {**BASE_SPEC}
    payload["assumptions"] = [
        {
            "id": "A-1",
            "statement": "Duplicate todos are forbidden",
            "basis": "unknown",
            "confidence": "unknown",
            "confirmation_required": True,
        }
    ]
    payload["cases"] = [
        {
            **BASE_SPEC["cases"][0],
            "oracles": [
                {
                    **BASE_SPEC["cases"][0]["oracles"][0],
                    "basis_ref": "A-1",
                }
            ],
        }
    ]

    with pytest.raises(ValidationError, match="unconfirmed assumption"):
        WorkflowTestSpec.model_validate(payload)


def test_truth_boundary_rejects_overlap() -> None:
    payload = {**BASE_SPEC}
    payload["truth_boundary"] = {
        "must_be_real": ["todo.create"],
        "may_be_mocked": ["todo.create"],
    }
    with pytest.raises(ValidationError, match="truth boundary overlaps"):
        WorkflowTestSpec.model_validate(payload)
