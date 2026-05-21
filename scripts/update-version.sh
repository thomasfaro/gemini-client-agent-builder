#!/usr/bin/env bash
# Update the version in manifest.json and pyproject.toml so they stay in sync.
# Usage: scripts/update-version.sh <version>   e.g. scripts/update-version.sh 1.1.0
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <version>" >&2
  exit 1
fi

version="$1"
if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.-]+)?$ ]]; then
  echo "Error: '$version' is not a valid semver version (e.g. 1.2.3 or 1.2.3-rc.1)" >&2
  exit 1
fi

root="$(cd "$(dirname "$0")/.." && pwd)"

bump() {
  local file="$1" pattern="$2" replacement="$3"
  python3 -c "
import re, sys
path, pattern, replacement = sys.argv[1:4]
text = open(path).read()
new, n = re.subn(pattern, replacement, text, count=1)
if n != 1:
    raise SystemExit(f'no version line matching {pattern!r} in {path}')
open(path, 'w').write(new)
" "$file" "$pattern" "$replacement"
}

bump "$root/manifest.json"   '"version":\s*"[^"]*"'        "\"version\": \"$version\""
bump "$root/pyproject.toml"  '(?m)^version\s*=\s*"[^"]*"'  "version = \"$version\""

echo "Updated to $version:"
echo "  manifest.json"
echo "  pyproject.toml"
echo "Next: update CHANGELOG.md, commit, then 'gtag v$version --public'."
