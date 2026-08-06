#!/usr/bin/env bash
set -euo pipefail

binary="${GITLEAKS_BIN:?GITLEAKS_BIN must point to the verified Gitleaks binary}"
workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT
repository="$workdir/repository"
report="$workdir/findings.json"
stdout_file="$workdir/stdout.log"
stderr_file="$workdir/stderr.log"

mkdir -p "$repository"
git -C "$repository" init -q
git -C "$repository" config user.name security-proof
git -C "$repository" config user.email security-proof@example.invalid

canary="$(python - <<'PY'
import secrets
import string

alphabet = string.ascii_letters + string.digits + "_"
print("github_pat_" + "".join(secrets.choice(alphabet) for _ in range(82)))
PY
)"
printf 'token=%s\n' "$canary" >"$repository/canary.txt"
git -C "$repository" add canary.txt
git -C "$repository" commit -q -m "add synthetic historical canary"
origin_commit="$(git -C "$repository" rev-parse HEAD)"
git -C "$repository" rm -q canary.txt
git -C "$repository" commit -q -m "remove synthetic historical canary"
test ! -e "$repository/canary.txt"

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

test "$status" -eq 42
grep -Fq "$origin_commit" "$report"
if grep -Fq "$canary" "$stdout_file" "$stderr_file" "$report"; then
  echo "Historical proof failed because the complete canary entered evidence." >&2
  exit 1
fi

echo "Historical synthetic-canary detection and complete redaction proof passed."
