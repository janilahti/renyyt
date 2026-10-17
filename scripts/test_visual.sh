#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
# Keep this image's Playwright version aligned with package.json. The digest fixes
# Chromium, fonts and native libraries; amd64 also fixes the rendering architecture.
visual_image='mcr.microsoft.com/playwright:v1.55.0-noble@sha256:ffc33305f7b4b04057ae4a0caa70aad4fde87454fb403a1a22e7f931707dfcf9'

docker run --rm --init --platform linux/amd64 --network none --shm-size 1g \
  --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$repo_root,dst=/work" --workdir /work \
  --env CI=1 --env SOURCE_DATE_EPOCH=1700000000 \
  --env npm_config_cache=/tmp/npm-cache --env XDG_CACHE_HOME=/tmp/cache \
  "$visual_image" bash -c \
  'python3 scripts/build.py && npm run test:visual:runner -- "$@"' -- "$@"
