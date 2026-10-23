#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
# Keep this image's Playwright version aligned with package.json. The digest fixes
# Chromium, fonts and native libraries; amd64 also fixes the rendering architecture.
visual_image='mcr.microsoft.com/playwright:v1.64.1-noble@sha256:47b510dd9230bf0b9bfc9b20102241e577ea7a99334ab4c3ca19f19770e9b8ea'

docker run --rm --init --platform linux/amd64 --network none --shm-size 1g \
  --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$repo_root,dst=/work" --workdir /work \
  --env CI=1 --env SOURCE_DATE_EPOCH=1700000000 \
  --env npm_config_cache=/tmp/npm-cache --env XDG_CACHE_HOME=/tmp/cache \
  "$visual_image" bash -c \
  'python3 scripts/build.py && npm run test:visual:runner -- "$@"' -- "$@"
