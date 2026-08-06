#!/usr/bin/env bash
set -euo pipefail

binary="${GITLEAKS_BIN:?GITLEAKS_BIN must point to the verified Gitleaks binary}"
repository="${1:-.}"
workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT
report="$workdir/findings.json"
stdout_file="$workdir/stdout.log"
stderr_file="$workdir/stderr.log"

set +e
"$binary" git \
  --log-opts="--all" \
  --redact=100 \
  --no-banner \
  --no-color \
  --log-level=error \
  --report-format=json \
  --report-path="$report" \
  --exit-code=42 \
  "$repository" >"$stdout_file" 2>"$stderr_file"
status=$?
set -e

case "$status" in
  0)
    echo "Gitleaks full-history scan completed with zero findings."
    ;;
  42)
    python scripts/security/summarize_gitleaks.py "$report"
    echo "Secret scan failed closed. Review findings without copying secret values." >&2
    exit 1
    ;;
  *)
    echo "Gitleaks failed before producing an authoritative verdict (status ${status})." >&2
    exit "$status"
    ;;
esac
