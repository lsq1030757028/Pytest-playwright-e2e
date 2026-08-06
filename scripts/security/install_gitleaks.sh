#!/usr/bin/env bash
set -euo pipefail

version="${GITLEAKS_VERSION:-8.30.1}"
expected_sha="${GITLEAKS_SHA256:-551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb}"
destination="${1:-${RUNNER_TEMP:-/tmp}/security-bin/gitleaks}"

if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
  echo "Unsupported platform for the pinned Gitleaks archive." >&2
  exit 2
fi

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT
archive="$workdir/gitleaks.tar.gz"
url="https://github.com/gitleaks/gitleaks/releases/download/v${version}/gitleaks_${version}_linux_x64.tar.gz"

curl --fail --location --silent --show-error --retry 3 --output "$archive" "$url"
printf '%s  %s\n' "$expected_sha" "$archive" | sha256sum --check --status

tar -xzf "$archive" -C "$workdir" gitleaks
install -D -m 0755 "$workdir/gitleaks" "$destination"
"$destination" version >/dev/null

echo "Installed Gitleaks ${version} after SHA-256 verification."
