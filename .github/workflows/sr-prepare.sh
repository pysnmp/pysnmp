#!/usr/bin/env bash

set -eE
set -v
echo "Preparing release: building distributions for version ${1:-unknown}"

rm -rf dist

# semantic-release has just rewritten the version in pyproject.toml, so uv.lock
# still records the previous one. CI installs with `uv run --locked`, which
# fails on that skew, so refresh the lockfile before building.
uv lock

uv build

echo "Distribution files prepared for publishing:"
ls -la dist/
