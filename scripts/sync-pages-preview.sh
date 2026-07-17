#!/usr/bin/env bash
# Optional: copy the V1 frontend into docs/ for manual /docs-folder Pages preview.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/docs"
cp "$ROOT/app/static/index.html" "$ROOT/docs/index.html"
touch "$ROOT/docs/.nojekyll"
echo "Synced app/static/index.html -> docs/index.html"
