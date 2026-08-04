from pathlib import Path

from test_workflow.models import QualityGate
from test_workflow.reporting import parse_junit, render_markdown


def test_report_marks_skipped_suite_as_pass_with_risk(tmp_path: Path) -> None:
    junit = tmp_path / "junit.xml"
    junit.write_text(
        '<testsuite tests="3" failures="0" errors="0" skipped="1" time="1.25"/>',
        encoding="utf-8",
    )

    summary = parse_junit(junit)

    assert summary.gate == QualityGate.PASS_WITH_RISK
    assert "PASS_WITH_RISK" in render_markdown(summary)
