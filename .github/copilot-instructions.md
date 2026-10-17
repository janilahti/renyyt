# Copilot instructions for Renyy

Follow the canonical repository guidance in `AGENTS.md`.

Key requirements:
- Preserve Python 3.8+ compatibility and avoid new runtime dependencies unless explicitly justified.
- Never log, commit, or expose credentials or customer data.
- Keep CSP strict: no inline JavaScript or inline style attributes.
- Keep the Python server stateless with respect to user credentials.
- Preserve base-path, reverse-proxy, embed, Prometheus/OpenMetrics, and accessibility behavior.
- Add regression tests for bug fixes and run the complete relevant test suite before proposing a release artifact.
- Keep generated files under `dist/`; source-of-truth frontend files are under `web/`.
- Release archives are named `renyyt-<version>.tar.gz` and contain a top-level `renyyt/` directory.
- Keep README and CHANGELOG synchronized with behavior changes.
