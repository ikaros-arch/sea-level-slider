#!/usr/bin/env bash
# Build a clean Sea Level Slider plugin .zip for upload to plugins.qgis.org.
#
# Uses `git archive`, so ONLY committed, tracked files are included and anything marked
# `export-ignore` in .gitattributes (scripts/, .git*, etc.) plus everything in .gitignore
# (__pycache__/, *.pyc, .venv/ …) is automatically left out. The archive is prefixed with
# `sea_level_slider/` so the zip has the required single top-level plugin folder.
#
# Usage:  bash scripts/make_zip.sh            # builds from HEAD (commit your changes first!)
#         bash scripts/make_zip.sh <git-ref>  # builds from a tag/branch/commit
set -euo pipefail

cd "$(dirname "$0")/.."          # repo root (the plugin folder)

REF="${1:-HEAD}"
VERSION="$(grep -E '^version=' metadata.txt | head -1 | cut -d= -f2 | tr -d '[:space:]')"
OUT="sea_level_slider-${VERSION}.zip"

# Warn if there are uncommitted changes — git archive won't include them.
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "WARNING: uncommitted changes exist; the zip is built from '${REF}', not the working tree." >&2
fi

rm -f "$OUT"
git archive --format=zip --prefix=sea_level_slider/ -o "$OUT" "$REF"

echo "Wrote $OUT"
echo "Contents (top level):"
unzip -l "$OUT" | grep -E "sea_level_slider/[^/]+/?$" || true
