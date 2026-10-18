# Renyyt development plan

Status reviewed after PR #9 (2026-10-18). Keep changes small and reviewable;
maintain green CI before adding features. The GitHub baseline is 0.8.0.
Version bumps remain patch-only when a release is actually needed.

## Completed quality gates

- [x] Python 3.8/3.13 tests, Ruff, branch coverage (minimum 78%), ESLint and frontend helpers.
- [x] Production build, installed-package smoke checks, reproducible archive/wheel and container readiness/shutdown checks.
- [x] Functional browser coverage on Chromium and Firefox.
- [x] Mobile layout/touch checks at 320, 390 and 430 pixels, including dialogs and embed.
- [x] Stable Chromium visual comparisons: Finnish at 320/430/768/1280 and Arabic at 320/1280, both light/dark; 72 baselines compared twice.
- [x] Arabic and Persian RTL: logical layout, mixed-direction isolation, dates, keyboard controls, dialogs, ordering and embed.
- [x] Vietnamese and Simplified Chinese (`zh-Hans`, `zh-CN`), with mobile/tablet/desktop functional checks and IME handling.
- [x] Manual ordering in normal view, compact/embed order preservation and space-efficient desktop controls.

These are ongoing regression requirements, not work to repeat from scratch.
Screenshot languages remain Finnish and Arabic; other languages have functional coverage.

## Next: distribution package investigation

- [ ] Compare Linux `.deb`/`.rpm`, Windows MSI/MSIX and macOS `.pkg`; consider `.dmg` if useful.
- [ ] Decide explicitly whether each format bundles Python or relies on the system Python.
- [ ] Assess installation/update/removal, configuration, service integration, signing and reproducibility.
- [ ] Document a recommended first target and implementation scope before adding installers.

A source archive and Python package already exist. Native OS packages are not implemented.
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
- [ ] Filter Chrome's `/.well-known/appspecific/com.chrome.devtools.json` 404 from access logs if useful; no endpoint is needed.

## Working rules

[AGENTS.md](AGENTS.md) remains the canonical engineering guidance.
[TESTING.md](TESTING.md) records validation commands and CI selection.
Keep completed gates green; do not claim GitHub verification based only on local results.
Maintenance and documentation changes do not automatically create a release or change VERSION.
