# Changelog

All notable changes to Renyyt are documented in this file.

The project uses semantic versioning. Versions before 1.0.0 are considered pre-release
development versions, so functionality and configuration may still change between minor
releases.

## Unreleased

### Added
- Vietnamese and Simplified Chinese (`zh-Hans`, `zh-CN`) interface translations,
  with Chromium/Firefox mobile, tablet and desktop layout coverage. Screenshot
  references remain Finnish and Arabic.
- Persian/Farsi as the second RTL interface language, with complete translations,
  Gregorian collection dates and Persian digits, plus Chromium/Firefox functional
  coverage. Arabic remains the only RTL screenshot language.
- Arabic as the first RTL interface language, including complete translations,
  logical layout alignment, isolated mixed-direction and technical values,
  Chromium/Firefox regressions and 24 Arabic light/dark visual baselines.
- Chromium visual regressions with 48 reviewed light/dark baselines at 320, 430,
  768 and 1280 pixels for
  login, results, bin selection, feedback, reminders and compact embed. A pinned
  renderer container, fixed fixture clock and repeated CI comparisons keep
  rendering conditions stable; Firefox remains a functional-test target.
- Responsive browser regressions at 320, 390 and 430 pixels for login, results,
  bin selection, feedback/reminder dialogs and compact embed, including translated
  headers, touch targets, overlap checks and dialog focus restoration.
- Run the complete functional Playwright suite on Firefox as well as Chromium,
  including browser installation in CI and documented per-browser commands.

### Fixed
- Do not submit credentials when Enter confirms an IME input candidate, including
  legacy composition key code 229; normal Enter sign-in remains available.
- Stack mobile bin-selection fields below their labels so inherited visibility
  values remain readable instead of being truncated by the native select. Give
  the order selector its own row on the narrowest screens for longer translations.
- Enlarged mobile controls and checkbox labels to 44-pixel touch targets. Stack
  narrow-screen card dates and wrap bin-selection controls and dialog headings
  so translated content stays inside its panel. Give narrow header selectors
  enough room for their selected text and keep saved-credential help on its own row.
- Keep API date interception out of the offline-shell regression so Firefox can
  reload through its service worker; assert that the offline response comes from it.
- Corrected ESLint globals for the shared Node/browser helpers and browser test callbacks.
- Updated browser regressions for translated date labels, drag handles, compact login
  controls, and the distinction between saved-credential and portable embed links.
- Made browser fixture dates relative to the test run and fixed the browser timezone.
- Fixed reminder-test discovery in a clean source checkout without an editable install.
- Made CI archive inspection preserve failures without shell-pipeline/SIGPIPE ambiguity
  and explicitly installed the tools needed by the reproducible-wheel check.

### Changed
- Use Python 3.13 for the application container. Skip browser installation,
  functional E2E and visual comparisons for changes confined to Dockerfile and
  .dockerignore; retain Python, quality, build and container runtime checks.
- Simplified the CI Python matrix to 3.8 and 3.13, moving installed-package,
  release-archive, reproducibility and quality checks from 3.11 to 3.13. The
  release workflow also uses Python 3.13.
- Updated GitHub Actions to Node 24-based versions and pinned CI/release runners to
  Ubuntu 24.04 so runner-image migrations do not silently change the baseline.
- Recorded development priorities and architecture boundaries in `AGENTS.md` and
  `ROADMAP.md`. Version changes are limited to the patch component for now.

## 0.8.0

### Added
- Web Push reminders for upcoming waste-bin collections.
- Optional SQLite reminder store with both an internal scheduler and external `run-due`
  execution for cron, systemd timers and cloud schedulers.
- VAPID key generation and reminder status commands in the `renyyt` CLI.
- Per-bin controls for normal visibility, embed visibility and reminder eligibility.
- Portable embed-view state in the URL, including selected bins, ordering and compact mode.

### Changed
- Embed links are now self-contained enough to be moved to another device without relying
  on that device's browser storage for view settings.
- Bin identifiers use a more stable fallback that does not depend on the next collection date.
- Reminder synchronization only includes bins currently eligible for reminders.
- Calendar export follows the bins visible in the normal view.

### Fixed
- Several embed-state and bin-selection edge cases.

## 0.7.0

### Added
- JSON fixture mode for backend and end-to-end testing.
- Browser-side JSON import for testing the normal rendering path without the live upstream.
- `TESTING.md` with the recommended local and CI test workflow.
- Reproducible release archive and wheel checks using `SOURCE_DATE_EPOCH`.
- Expanded malformed-HTTP regression coverage.

### Changed
- Upstream login/session handling was hardened against unexpected redirects and login-form
  responses.
- TRACE logging now records upstream bodies only after they have successfully parsed as JSON.
- API responses expose upstream fetch time, data age and data source metadata.
- UI update timestamps distinguish cached data from genuinely fresh upstream data.

### Fixed
- Prevented HTML or JavaScript responses from being written to API TRACE logs even when an
  upstream server advertises an incorrect JSON content type.
- Improved handling of malformed, truncated and ambiguous HTTP requests.

## 0.6.0

### Added
- Optional Progressive Web App support with installable app shell.
- Offline fallback to the last successfully fetched collection data.
- Optional browser-side storage of credentials.
- Shareable embed mode.
- Finnish, English, Swedish and Ukrainian UI translations.

### Changed
- Stored and embedded credentials use a versioned Web Crypto AES-GCM obfuscation blob instead
  of plain-text or simple Base64 representation.
- The application explicitly describes this mechanism as obfuscation rather than secure
  encryption because the decryption material travels with the blob.
- Service worker caching was simplified so navigation responses use the installed app shell
  rather than fragile runtime cloning.
- PWA behavior can be completely disabled with configuration.

### Fixed
- Service worker `Response.clone()` race/regression issues.
- Translation and embed-view UI inconsistencies.

## 0.5.0

### Added
- Built-in `.env` loading without an additional runtime dependency.
- `renyyt --check` diagnostics for configuration and optional features.
- Optional SMTP feedback with safe DEBUG diagnostics and intentionally sensitive TRACE mode.
- Optional in-memory upstream response cache with TTL, LRU eviction, byte limit and
  per-key single-flight request coalescing.
- Feedback attachment support for explicitly approved collection JSON.

### Changed
- All application configuration uses the `RENYYT_*` environment-variable prefix.
- Cache keys use process-random HMAC-SHA256 rather than exposing credential-derived values.
- Logging levels and security boundaries were clarified and regression-tested.
- Feedback email handling supports a validated Reply-To address.

### Fixed
- Credentials and other sensitive values are excluded from DEBUG logging.
- SMTP timeout and connection errors now map to more appropriate HTTP error responses.

## 0.4.0

### Added
- Initial consolidated Renyyt application structure:
  - lightweight Python web server and proxy
  - browser UI for upcoming waste-bin collection dates
  - `/api/v1/renyyt` API
  - `renyyt` command-line entry point
  - Docker and reverse-proxy deployment documentation
  - calendar export and basic browser-side preferences

### Changed
- Project, package, CLI and API naming was unified under **Renyyt / `renyyt`**.
- The old technical `renyy` naming was removed; **Renyy** remains only when referring to
  Pirkanmaan Jätehuolto's Renyy service.
- The upstream integration was documented as a three-step session flow:
  session initialization, form login and JSON service retrieval.

### Security
- Upstream credentials are sent only to the local Renyyt proxy and are not stored by the
  server.
- Upstream redirects and response types are validated before data is accepted.
