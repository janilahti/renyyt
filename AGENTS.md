# AI and Contributor Engineering Guide

This file is the canonical engineering guidance for AI coding agents and human contributors working on **Renyy**.

## Project principles

- Keep the application small, self-hostable, privacy-conscious, and dependency-light.
- Preserve Python **3.8+** compatibility unless the project explicitly changes its supported versions.
- Do not add runtime dependencies without a clear, documented benefit. Prefer the Python standard library and browser-native APIs.
- Finnish is the default UI language, but every new user-facing string must be added to all currently supported UI languages in `web/i18n.js`. Developer documentation and code comments may be English.
- The primary application API is `/api/v1/renyyt`. Endpoint compatibility is not guaranteed unless explicitly documented.
- Treat the upstream Renyy/Pirkanmaan Jätehuolto API as undocumented and changeable. Be permissive about unknown fields, strict only where malformed data makes safe interpretation impossible.

## Security and privacy

- Never commit, log, test with, or expose real customer numbers, passwords, email addresses, phone numbers, addresses, or raw customer payloads.
- Credentials must not be persisted by the Python server. Browser credential storage is opt-in; Base64 storage is obfuscation, **not encryption**.
- Do not weaken Origin/Host checks, trusted-proxy handling, CSP, request-size limits, rate limiting, or security headers without an explicit security review.
- Metrics and logs must not use credentials or customer data as labels or fields.
- Unknown-field diagnostics may record field names and structural types only, never values or nested personal-data structures.
- Preserve the ability to embed the UI. Do not add `X-Frame-Options` or restrictive `frame-ancestors` rules without deliberately revisiting the embed use case.

## Architecture and source layout

- Python application code lives under `src/renyyt/`.
- Browser source files live under `web/`.
- Generated production assets live under `dist/` and are not source-of-truth files.
- Build and release tooling lives under `scripts/`.
- Tests live under `tests/`.
- Deployment examples live under `deploy/`.
- Repository automation and templates live under `.github/`.
- The repository URL is `https://github.com/janilahti/renyyt`.

## Frontend rules

- Keep CSP compatible with `script-src 'self'` and `style-src 'self'`; do not reintroduce inline JavaScript or inline style attributes.
- Keep pure reusable frontend logic in `web/helpers.js` when practical and cover it with `tests/test_frontend.js`.
- A failure while rendering one waste service must not prevent other services from rendering.
- Maintain keyboard operation, visible focus states, reduced-motion support, forced-colors/high-contrast behavior, and responsive layouts.
- Ordinary informational/error notices align left. Fetch progress states such as `Haetaan…` / `Valmis` may use the dedicated right-aligned status position.
- Preserve light/dark/system theme support, embed behavior, and the opt-in PWA install flow. Installed launches must continue to open the embed view without forcing an install prompt.

## HTTP and deployment rules

- The server must remain usable directly and behind a reverse proxy/base path.
- Respect `RENYYT_BASE_PATH`, trusted proxy configuration, and the standard container `PORT` fallback.
- Static resources may use adjacent precompressed `.gz` representations. Never gzip dynamically in Python; use a precompressed file only when the client advertises `Accept-Encoding: gzip`.
- In normal reverse-proxy production deployments, prefer proxy-level gzip/Brotli and omit precompressed `.gz` files from the Python deployment.
- Fingerprinted production assets are immutable and may receive long-lived cache headers. HTML and documentation use revalidation (`no-cache`). API/health/metrics responses that must not be cached remain `no-store`.
- Keep Prometheus text exposition and OpenMetrics support working in parallel.

## Tests and validation

Before presenting or publishing a release artifact, run the complete applicable test suite. At minimum:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
node tests/test_frontend.js
python3 scripts/build.py
python3 -m compileall -q src scripts run.py
node --check web/helpers.js
node --check web/app.js
```

Add regression tests whenever fixing a bug or adding behavior that can be tested reasonably. Do not merely update a failing test to match a regression.

For packaging changes, test the generated archive contents. For Python packaging changes, test an installed wheel in a clean environment when practical. Container-specific behavior should be covered by CI when Docker is unavailable locally.

## Build and release rules

- Source assets keep stable development names (`i18n.js`, `app.js`, `helpers.js`, `styles.css`).
- `scripts/build.py` generates fingerprinted production assets under `dist/`.
- `scripts/build.py --gzip` may generate adjacent precompressed `.gz` files for standalone deployment; release source archives do not include generated `.gz` files.
- Release archives use the top-level directory name `renyyt/` and filenames `renyyt-<version>.tar.gz`.
- Update `VERSION` and `CHANGELOG.md` for releases. Tags must match `v$(cat VERSION)`.
- Do not commit generated caches, wheels, egg-info, `__pycache__`, or release tarballs.

## Documentation

- Keep README examples synchronized with actual environment variables, paths, endpoints, cache behavior, deployment layout, and packaging commands.
- Prefer complete, copyable examples, but never include real credentials.
- If behavior changes in a way relevant to operators or users, update README and CHANGELOG in the same change.

## Scope discipline

- Prefer small, reviewable changes over framework rewrites.
- Avoid speculative abstractions. Add modules when responsibilities are genuinely separable.
- Preserve existing behavior unless the change is deliberate and documented.
- When uncertain about upstream API semantics, expose raw data or diagnostics rather than inventing meaning.
