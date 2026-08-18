#!/usr/bin/env bash
set -euo pipefail

version=${1:?version required}
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
target="${root}/romimage/version.py"

if ! grep -q '^VERSION = "' "$target"; then
  printf 'no VERSION assignment found in %s\n' "$target" >&2
  exit 1
fi

tmp=$(mktemp "${TMPDIR:-/tmp}/nochip-version-XXXXXX")
sed "s/^VERSION = \".*\"$/VERSION = \"${version}\"/" "$target" >"$tmp"
mv "$tmp" "$target"

printf 'version set to %s\n' "$(grep '^VERSION = ' "$target" | cut -d'"' -f2)"
