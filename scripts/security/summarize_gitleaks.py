from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SAFE_TEXT = re.compile(r"[^A-Za-z0-9._/@:+-]")
MAX_FINDINGS = 20


def sanitized(value: object, *, limit: int = 180) -> str:
    text = str(value or "unknown").replace("\n", "?").replace("\r", "?")
    return SAFE_TEXT.sub("?", text)[:limit]


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: summarize_gitleaks.py REPORT.json", file=sys.stderr)
        return 2

    report_path = Path(sys.argv[1])
    findings = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(findings, list):
        print("Gitleaks report has an unexpected shape.", file=sys.stderr)
        return 2

    print(f"Gitleaks detected {len(findings)} finding(s); secret values are omitted.")
    for finding in findings[:MAX_FINDINGS]:
        if not isinstance(finding, dict):
            continue
        rule = sanitized(finding.get("RuleID"))
        path = sanitized(finding.get("File"))
        line = sanitized(finding.get("StartLine"), limit=20)
        commit = sanitized(finding.get("Commit"), limit=40)
        fingerprint = sanitized(finding.get("Fingerprint"))
        print(
            "finding "
            f"rule={rule} path={path} line={line} "
            f"commit={commit} fingerprint={fingerprint}"
        )

    if len(findings) > MAX_FINDINGS:
        print(f"{len(findings) - MAX_FINDINGS} additional finding(s) omitted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
