#!/usr/bin/env bash
# Optional: copy the V1 frontend into docs/ for manual /docs-folder Pages preview.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/docs"
cp "$ROOT/v1-migration-backend/public/index.html" "$ROOT/docs/index.html"
cp "$ROOT/v1-migration-backend/public/index.html" "$ROOT/index.html"
touch "$ROOT/docs/.nojekyll"
echo "Synced v1-migration-backend/public/index.html -> docs/index.html and index.html"
