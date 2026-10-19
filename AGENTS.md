# AI and Contributor Engineering Guide

This file is the canonical engineering guidance for AI coding agents and human contributors working on **Renyyt**.

## Project principles

- The technical project name is **Renyyt / renyyt**. **Renyy** refers only to the upstream Pirkanmaan Jätehuolto service/brand.
- The GitHub baseline is **0.8.0**. The old internal 1.16–1.24 history was consolidated into 0.4.0–0.8.0 before import; do not resume that numbering.
- Version 1.0.0 is explicitly authorized for this release. After it, default version changes increment only the final component (for example, 1.0.0 → 1.0.1). Do not bump the minor or major version without a new user decision. Maintenance work does not automatically require a release.
- Follow `ROADMAP.md`: CI, responsive/visual/Firefox and Arabic/Persian RTL gates are implemented and must stay green. Linux deb/rpm base packaging uses system Python 3.8+, retains settings/data on removal and provides explicit purge; Windows/macOS packaging remains an investigation; native mobile/widgets remain a separate investigation. Fix CI findings before adding large features.
- Keep the application small, self-hostable, privacy-conscious, and dependency-light.
- Preserve Python **3.8+** compatibility unless the project explicitly changes its supported versions.
- Do not add runtime dependencies without a clear, documented benefit. Prefer the Python standard library and browser-native APIs.
- Feature-specific dependencies should use optional extras where practical.
- Keep short `README.<language>.md` guides in sync with supported UI languages and include them in both runtime/wheel data and archives.
- Finnish is the default UI language, but every new user-facing string must be added to all currently supported UI languages in `web/i18n.js`. Developer documentation and code comments may be English.
- The primary application API is `/api/v1/renyyt`. Endpoint compatibility is not guaranteed unless explicitly documented.
- Treat the upstream Renyy/Pirkanmaan Jätehuolto API as undocumented and changeable. Be permissive about unknown fields, strict only where malformed data makes safe interpretation impossible.

## Security and privacy

- Never commit, log, test with, or expose real customer numbers, passwords, email addresses, phone numbers, addresses, or raw customer payloads.
- Credentials must not be persisted by the Python server. Browser credential storage is opt-in; the AES-GCM credential blob is obfuscation, **not secure encryption**, because its key travels with it.
- The reminder store contains push subscriptions and collection snapshots, never upstream customer numbers or passwords.
- DEBUG must never include credentials or request/response bodies. API TRACE may log only successfully parsed JSON, never upstream HTML, even if its Content-Type claims JSON.
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
- Ordinary informational/error notices align to the inline start (left in LTR, right in RTL). Fetch progress states such as `Haetaan…` / `Valmis` may use the dedicated inline-end status position.
- Preserve light/dark/system theme support, embed behavior, and the opt-in PWA install flow. Installed launches must continue to open the embed view without forcing an install prompt.
- Keep embed `view=` state portable across devices: selected bins, ordering, and compact mode must travel in the URL rather than depend on localStorage at the destination.
- Manual reordering is exclusive to normal view. Compact and embed views preserve the selected order without edit controls or dragging; expanded desktop details get the full card width.
- Bin keys must remain stable when collection dates change; never include the next collection date in a stable key.
- Service-worker navigation response cloning has caused races before. Do not reintroduce aggressive navigation runtime caching without regression coverage.

## HTTP and deployment rules

- The server must remain usable directly and behind a reverse proxy/base path.
- Keep Caddy/nginx route allowlists synchronized when adding endpoints, localized guides or public resources; preserve both root and subpath deployments.
- Respect `RENYYT_BASE_PATH`, trusted proxy configuration, and the standard container `PORT` fallback.
- Static resources may use adjacent precompressed `.gz` representations. Never gzip dynamically in Python; use a precompressed file only when the client advertises `Accept-Encoding: gzip`.
- In normal reverse-proxy production deployments, prefer proxy-level gzip/Brotli and omit precompressed `.gz` files from the Python deployment.
- Fingerprinted production assets are immutable and may receive long-lived cache headers. HTML and documentation use revalidation (`no-cache`). API/health/metrics responses that must not be cached remain `no-store`.
- Keep Prometheus text exposition and OpenMetrics support working in parallel.
- Preserve the upstream session-init → form-login → JSON-services sequence. HTML is normal in the first two steps; only the services endpoint is expected to return JSON.

## Tests and validation

Before presenting or publishing a release artifact, run the complete applicable test suite. At minimum:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
node tests/test_frontend.js
python3 scripts/build.py
python3 -m compileall -q src scripts deploy/linux run.py
node --check web/helpers.js
node --check web/app.js
```

Add regression tests whenever fixing a bug or adding behavior that can be tested reasonably. Do not merely update a failing test to match a regression.

Use relative dates for time-sensitive tests and freeze the clock when needed; tests must not expire as real time passes. Preserve byte-for-byte reproducibility under `SOURCE_DATE_EPOCH`, including metadata, timestamps, and generated artifacts.

For packaging changes, test the generated archive contents. For Python packaging changes, test an installed wheel in a clean environment when practical. Container-specific behavior should be covered by CI when Docker is unavailable locally.

For Markdown-only work, the lightweight CI checks documented in `TESTING.md` are
sufficient. They validate CI selection, local file links, runtime environment names,
production build and `--check`. Code/config/workflow changes require the applicable
full checks. Manual CI always runs the full suite. Do not weaken selection's
conservative fallback for missing history, unknown events, renames or mixed PRs.

## Build and release rules

- Source assets keep stable development names (`i18n.js`, `app.js`, `helpers.js`, `styles.css`).
- `scripts/build.py` generates fingerprinted production assets under `dist/`.
- `scripts/build.py --gzip` may generate adjacent precompressed `.gz` files for standalone deployment; release source archives do not include generated `.gz` files.
- Release archives use the top-level directory name `renyyt/` and filenames `renyyt-<version>.tar.gz` and `renyyt-<version>.zip`; both formats use the same payload/exclusions and fixed-epoch reproducibility.
- Update `VERSION` and `CHANGELOG.md` for releases. Tags must match `v$(cat VERSION)`.
- Native packages are architecture-independent (`all`/`noarch`), use systemd and suggest optional Web Push through `Suggests: python3-pywebpush` without a separate add-on package. Verify repository availability; never install with pip into distribution Python. Test lifecycle only in disposable containers/CI VMs; never install experimental packages on a working host. Preserve pre-existing service identities and distinguish remove from destructive purge.
- Do not commit generated deb/rpm packages, caches, wheels, egg-info, `__pycache__`, release tarballs or runtime SQLite data (including WAL/SHM). Keep private data outside the source tree; Git/Docker/archive ignore rules are an additional guard.

## Documentation

- Keep README examples synchronized with actual environment variables, paths, endpoints, cache behavior, deployment layout, and packaging commands.
- Prefer complete, copyable examples, but never include real credentials.
- If behavior changes in a way relevant to operators or users, update README and CHANGELOG in the same change.

## Scope discipline

- Prefer small, reviewable changes over framework rewrites.
- Avoid speculative abstractions. Add modules when responsibilities are genuinely separable.
- Preserve existing behavior unless the change is deliberate and documented.
- When uncertain about upstream API semantics, expose raw data or diagnostics rather than inventing meaning.
