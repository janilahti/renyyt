# Renyyt development plan

Work in small, reviewable steps. Finish each quality gate before moving to the next.
The GitHub baseline is 0.8.0; for now, releases change only the patch component.
The old internal 1.16–1.24 series was consolidated into 0.4.0–0.8.0 before GitHub import.

## 1. Establish a green GitHub Actions baseline

- Python regression tests and branch-aware coverage (minimum 78%).
- Ruff, ESLint, and frontend helper tests.
- Production build and `renyyt --check`.
- Reproducible release archive and wheel under `SOURCE_DATE_EPOCH`.
- Playwright functional tests and the existing container build.
- Run the complete workflow in GitHub Actions and fix all findings before large features.
- Do not equate a local passing run with a verified GitHub Actions run.

## 2. Expand browser and responsive regression coverage

After the CI baseline is green:

- Run all functional E2E tests on Chromium and Firefox.
- Keep visual regression tests and screenshot baselines on Chromium.
- Consider WebKit later as a Safari compatibility signal.
- Compare Chromium screenshots at 320, 430, 768, and 1280 pixels to cover narrow
  and wide phones, tablets, and desktop layouts.
- Run mobile layout and touch checks on Chromium and Firefox at 320, 390, and
  430 pixels. The 390-pixel case exercises the intermediate layout between the
  360- and 420-pixel CSS breakpoints without adding another screenshot set.
- Check horizontal overflow, overlapping elements, touch target sizes, and header layout.
- Cover login, results, the Astiat/bin-selection dialog, feedback dialog, reminders dialog,
  and embed view. Enable optional features through safe test configuration, without
  sending real feedback or push messages.
- Keep screenshot inputs, fonts, browser versions, clocks, and rendering conditions stable.

## 3. RTL support

Only after the preceding quality gates:

- Add and test `dir="rtl"`.
- Prefer logical CSS: `margin-inline-*`, `padding-inline-*`, `inset-inline-*`,
  and `text-align: start/end`.
- Isolate technical values as LTR where needed.
- Test icons, directional arrows, dialog button order, drag and drop, the header,
  and mixed-direction text. Do not add RTL languages without layout verification.

## 4. Distribution packages

- Investigate `.deb`, `.rpm`, Windows MSI/MSIX, and macOS `.pkg`.
- Consider `.dmg` if it improves installation/distribution.
- Decide explicitly whether to bundle a Python runtime or use the system Python.
- Preserve the dependency-light runtime and reproducible-build requirements.

## Mobile application investigation

Compare PWA, WebView/wrapper, Capacitor-style hybrid, Flutter/React Native, and native
implementations. Evaluate Keychain/Keystore credential handling, push notifications,
background refresh, widgets, and store distribution. A native home-screen widget is
a primary reason for this investigation, not an incidental enhancement.

Periodic Background Sync may provide opportunistic freshness. It must never be the
only reminder mechanism: Web Push plus the server scheduler remains the primary mechanism.

## Optional cleanup

Chrome's `/.well-known/appspecific/com.chrome.devtools.json` 404 can optionally be
filtered from access logs. There is no functional need to implement that endpoint.

## Architectural boundaries

`AGENTS.md` records the ongoing engineering rules: Renyyt/Renyy naming, optional
dependencies, upstream login stages, DEBUG/TRACE privacy, credential obfuscation,
no server-side upstream credential storage, reminder-store data limits, portable
embed state, stable bin identifiers, service-worker race prevention, relative test
dates, reproducible builds, and regression coverage for every bug fix.
