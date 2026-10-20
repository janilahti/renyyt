# Renyyt development plan

Status reviewed for the explicitly requested 1.0.1 release (2026-10-20). Keep changes small and reviewable;
maintain green CI before adding features. The GitHub baseline was 0.8.0; this release is 1.0.1.
Future version bumps default to patch-only unless explicitly decided otherwise.

## Completed quality gates

- [x] Python 3.8/3.13 tests, Ruff, branch coverage (minimum 78%), ESLint and frontend helpers.
- [x] Production build, installed-package smoke checks, reproducible archive/wheel and container readiness/shutdown checks.
- [x] Functional browser coverage on Chromium and Firefox.
- [x] Mobile layout/touch checks at 320, 390 and 430 pixels, including dialogs and embed.
- [x] Stable Chromium visual comparisons: Finnish at 320/430/768/1280 and Arabic at 320/1280, both light/dark; 72 baselines compared twice.
- [x] Arabic and Persian RTL: logical layout, mixed-direction isolation, dates, keyboard controls, dialogs, ordering and embed.
- [x] Estonian (`et`, `et-EE`), short README guides in all nine UI languages, and reproducible tar.gz/ZIP release packaging.
- [x] Vietnamese and Simplified Chinese (`zh-Hans`, `zh-CN`), with mobile/tablet/desktop functional checks and IME handling.
- [x] Manual ordering in normal view, compact/embed order preservation and space-efficient desktop controls.
- [x] Documentation/deployment review and lightweight Markdown CI, with conservative full checks for code/configuration and mixed changes.

These are ongoing regression requirements, not work to repeat from scratch.
Screenshot languages remain Finnish and Arabic; other languages have functional coverage.

## Distribution packages

- [x] OCI/GHCR publication workflow, initially linux/amd64; NuGet is out of scope.
- [x] New default port 18514, flat /etc/renyyt.env and native 1.0.0 migration checks.

- [x] Implement system-Python deb/all and rpm/noarch base packages for Debian/Ubuntu, Fedora and RHEL 9+ families.
- [x] Separate ordinary removal (retain settings/data) from explicit purge, with systemd integration and reproducible builds.
- [x] Suggest `python3-pywebpush` directly in deb/rpm metadata and document repository checks, isolated-venv fallback, VAPID keys and internal scheduling.
- [ ] Investigate Windows MSI/MSIX and macOS `.pkg`; consider `.dmg` if useful.
- [x] Linux packages rely on distribution Python 3.8+; no pip or bundled interpreter.
- [ ] Decide Python bundling for Windows/macOS.
- [ ] Assess Windows/macOS installation, updates, removal, signing and reproducibility.
- [ ] Add signed native package repositories if distribution demand warrants them.
- [x] Agree first targets, remove/purge semantics and base-only scope with the maintainer.

Source archives (tar.gz/ZIP), a Python package and native Linux packages are implemented.
Distribution lifecycle checks gate deb/rpm release assets; Windows/macOS installers remain unimplemented.
Preserve the small runtime and avoid unnecessary dependencies.

## Mobile application investigation

- [ ] Compare the existing PWA with WebView/wrappers, Capacitor-style hybrid, Flutter/React Native and native implementations.
- [ ] Evaluate Keychain/Keystore credential handling, Web Push/native push, background refresh and store distribution.
- [ ] Treat native home-screen widgets as a primary requirement, including their data refresh and privacy boundaries.
- [ ] Recommend an approach and scope before starting a mobile implementation.

The current PWA and Web Push reminders are implemented; native apps and widgets are not.
Periodic Background Sync may improve freshness but must never be the only reminder mechanism.
Web Push plus a server scheduler remains the current reminder design. Serverless reminders
would also require persistent shared storage beyond the current local SQLite implementation.

## Optional follow-up

- [ ] Add WebKit/Safari as another functional compatibility signal.
- [x] Reject unknown scan paths and Chrome's `/.well-known/appspecific/com.chrome.devtools.json` in proxy examples before Python. Direct Python access still returns/logs 404; no endpoint is needed.

## Working rules

[AGENTS.md](AGENTS.md) remains the canonical engineering guidance.
[TESTING.md](TESTING.md) records validation commands and CI selection.
Keep completed gates green; do not claim GitHub verification based only on local results.
Maintenance and documentation changes do not automatically create a release or change VERSION.
