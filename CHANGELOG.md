# Changelog

All notable changes to Renyyt are documented in this file.

The project uses semantic versioning. Versions before 1.0.0 are considered pre-release
development versions, so functionality and configuration may still change between minor
releases.

## Unreleased

### Fixed

- Populate About build time and Git commit from packaged build metadata, with
  a Git fallback for unbuilt source checkouts and existing environment overrides.
- Keep embed links created before the first fetch from accidentally hiding every
  bin; preserve intentionally empty selections and portable per-bin filters.

### Added

- Run functional, responsive and RTL browser tests on Playwright WebKit alongside
  Chromium and Firefox; screenshot comparisons remain Chromium-only. Isolate
  routed fixture tests from service workers, and verify WebKit offline fallback
  with dropped network connections instead of broken browser offline emulation.

## 1.0.1 – 2026-10-20

### Changed

- Change the default port from 8787 to 18514 across application/container defaults,
  deployment examples, localized guides and tests. Explicit port settings remain
  authoritative, including settings retained during upgrades.
- Move native-package settings to root-owned mode-0600 `/etc/renyyt.env`, migrate
  the 1.0.0 path safely, and preserve extra administrator files. Both formats use
  lifecycle-managed configuration instead of package-owned conffiles.

### Added

- Publish OCI images to GHCR from stable release commits, initially linux/amd64,
  with version/latest tags, least-privilege workflow authentication and a manual
  backfill for existing releases. Historical backfills preserve the latest alias.
- Validate OCI exports and real deb/rpm upgrades from 1.0.0, including migrated
  settings, retained explicit ports and safe purge.

## 1.0.0 – 2026-10-19

### Added

- Reject unknown paths in the Caddy/nginx examples before proxying to Python,
  preserving all application/PWA/API routes and documenting root/subpath use.
  Check route/language coverage against the server to catch allowlist drift.

- Optional commented Caddy/nginx static-file offload examples with strict asset
  allowlists, fingerprint-aware caching, security headers and subpath handling.
  Keep dynamic/PWA-sensitive routes proxied and document shared release paths.

### Fixed

- Offer explicit calendar export choices, visible download feedback, optional
  native file sharing and per-collection Google Calendar event forms for Android.
  Export only selected bins; explain that events are snapshots and not a sync.
- Generate RFC 5545 calendar files with UTC DTSTAMP, exclusive all-day DTEND,
  validated dates, escaped text and UTF-8-aware 75-octet line folding.

- Size collection metadata badges to their text instead of stretching them to
  adjacent disclosure controls; retain 44-pixel mobile disclosure touch targets.

- Keep long dialogs within the dynamic mobile viewport, with a visible opening
  header and close button when browser toolbars reduce the available height.
  Lock background scrolling while any dialog is open and restore it on close.

- Require a customer number and password saved in the browser before opening the
  PWA install prompt or iOS instructions. Keep Install visible and show translated
  saving instructions when credentials are missing or no longer stored.

### Packaging

- Architecture-independent deb/rpm base packages for Debian/Ubuntu, Fedora and RHEL 9+ families, using distribution Python 3.8+ and a hardened systemd service.
- Preserve settings and data on ordinary removal; provide explicit purge, including a retained shell cleanup command after uninstall. Preserve pre-existing service identities.
- Reproducible native builds, isolated distribution lifecycle checks and tagged-release deb/rpm assets. Web Push is optional through direct `Suggests: python3-pywebpush`, with repository checks and isolated-venv fallback instructions.

- Create Debian active configuration through lifecycle hooks rather than a dpkg conffile, preventing Debian purge from following a configuration symlink and deleting its external target.

- Keep optional native-package dependencies under `/opt/renyyt/venv`; refuse purge before deleting data if a package-created identity has changed. Test preservation of unrelated files and symlink targets in actual distribution lifecycle checks.

## 0.9.0 – 2026-10-18

### Added
- Estonian (`et`, `et-EE`) as the ninth interface language, with mobile/tablet/desktop
  functional coverage on Chromium and Firefox.
- Short localized README guides in all nine UI languages, opened in the selected
  language by the README button, with RTL Arabic/Persian document layout.
- Reproducible ZIP release archives alongside tar.gz, identical payload/exclusions
  and SHA-256 checksums. Release artifacts include the localized guides.
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
- Render HTTP(S) Markdown autolinks in the documentation dialog while preserving
  literal inline code and escaped HTML.
- Honor RENYYT_PORT before PORT in the container healthcheck, including base-path
  deployments. Verify both default and overridden configurations in CI.
- Exclude local SQLite databases and sidecars plus developer caches from Git,
  Docker context and source archives; keep reminder data out of distributable files.
- Align systemd HTTP/reminder units on an installed virtualenv, private persistent
  state and read-only application files; correct proxy/base-path deployment guidance.
- Preserve manual bin order in compact view while keeping reordering exclusive to
  normal view. On wide screens, place the controls beside the details summaries
  and hide them while either details section is open so its content gets full width.
- Give the manual-order selector enough width for its label and native arrow in
  Firefox on desktop.
- Give Vietnamese mobile language/theme selectors a full row so their labels and
  selected values stay readable across browser fonts.
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
- Consolidate README around user workflows, move operator detail to TECHNICAL,
  update API/security/testing/contributor guidance and mark completed roadmap gates.
- Use lightweight documentation checks for Markdown-only pushes/PRs: local file
  links, environment-name coverage, CI-selection regressions, build and --check.
  Retain full checks for mixed/code/config/workflow changes and manual runs;
  container-only changes may also include Markdown without triggering browsers.
- Use Python 3.13 for the application container. Skip browser installation,
  functional E2E and visual comparisons for changes confined to Dockerfile and
  .dockerignore; retain Python, quality, build and container runtime checks.
- Simplified the CI Python matrix to 3.8 and 3.13, moving installed-package,
  release-archive, reproducibility and quality checks from 3.11 to 3.13. The
  release workflow also uses Python 3.13.
- Updated GitHub Actions to Node 24-based versions and pinned CI/release runners to
  Ubuntu 24.04 so runner-image migrations do not silently change the baseline.
- Recorded development priorities and architecture boundaries in `AGENTS.md` and
  `ROADMAP.md`. The default remains patch-only version bumps; 0.9.0 was explicitly requested for this release.

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
