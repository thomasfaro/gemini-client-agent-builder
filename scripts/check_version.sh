#!/usr/bin/env bash
# Validate that a release tag matches the version in manifest.json.
# Usage: scripts/check_version.sh <tag>
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <tag>" >&2
  exit 1
fi

tag="$1"
root="$(cd "$(dirname "$0")/.." && pwd)"
manifest_version=$(python3 -c "import json; print(json.load(open('$root/manifest.json'))['version'])")

if [[ "$tag" != "$manifest_version" ]]; then
  echo "Error: tag '$tag' does not match manifest.json version '$manifest_version'" >&2
  exit 1
fi
