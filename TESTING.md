# Testing Renyyt

This document collects the project's local development and CI test commands in one place.
The application itself has no runtime dependency on Node.js, Playwright, Ruff, ESLint or coverage.py; those tools are development and CI dependencies only.

## Prerequisites

- Python 3.8 or newer
- Node.js 20 recommended for the JavaScript quality and browser test suite
- A normal network connection when installing development dependencies or Playwright browsers

Create a Python virtual environment and install the development extras:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
```

Install JavaScript development dependencies:

```bash
npm install
```

## Python regression tests

Run the complete Python test suite:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
```

Run an individual module when iterating on one area:

```bash
PYTHONPATH=src python3 -m unittest -v tests.test_server
```

## Coverage

The CI baseline is 78 percent branch-aware coverage:

```bash
PYTHONPATH=src coverage run --branch -m unittest discover -s tests -p 'test_*.py'
coverage report --fail-under=78
```

Coverage is a regression guard, not a statement that every line requires a test. New behavior should normally include a focused regression test.

## Ruff

Run Python lint checks with:

```bash
ruff check src tests scripts run.py
```

## Frontend unit tests and ESLint

Run the dependency-free frontend helper tests with:

```bash
npm run test:frontend
```

Run JavaScript linting with:

```bash
npm run lint:js
```

The raw syntax checks used by CI can also be run directly:

```bash
node --check web/helpers.js
node --check web/app.js
node --check web/i18n.js
```

## Playwright end-to-end tests

Install Chromium and Firefox for Playwright once:

```bash
npx playwright install --with-deps chromium firefox
```

Then run the functional browser suite on both browsers:

```bash
npm run test:e2e
```

The E2E suite starts the real Renyyt HTTP server and uses `RENYYT_FIXTURE_FILE` instead of the external Oma jätehuolto service. This means the browser, HTTP API, validation and rendering paths are tested together without requiring real credentials or an external network dependency.

Browser tests freeze the clock at the current week's Monday in UTC and adjust only
the fixture response's collection dates relative to that day. Date-label assertions
therefore do not expire or depend on the runner's timezone. The tests cover saved
credentials, translations, drag handles and move buttons, saved-credential embed
links, portable credential/view links in a fresh browser context, documentation
links, install UI, a narrow header, and the offline service-worker shell. CI always
starts its own fixture server and uploads browser failure traces. The offline-shell
case removes the unused API date interception because routing disables Firefox's
cache and bypasses its service worker on reload. It verifies the response was
served by the service worker while the browser is offline.

CI and release workflows use Ubuntu 24.04 and Node.js 24. Runner OS upgrades are
explicit changes so browser and build dependencies do not move with `ubuntu-latest`.

All functional E2E tests run on Chromium and Firefox locally and in CI. To run
just one browser, use `npm run test:e2e -- --project=firefox` (or `chromium`).
Responsive tests run on both browsers at widths of 320, 390 and 430 CSS
pixels, with touch input enabled. They check horizontal overflow, overlapping
controls, header/card/dialog content, selected option text, saved-credential
help layout and 44-by-44 CSS-pixel touch targets (native
checkboxes use their labels). Header and login checks cover all six UI languages;
results, manual ordering, bin selection and feedback/reminder dialogs cover
Finnish, Ukrainian, Arabic and Persian. Compact embed is also checked at each width. Dialog tests
exercise touch operation and focus restoration. Optional feature flags are mocked; feedback and reminder
writes are blocked and fail the test if attempted.

Run only these checks with `npm run test:e2e -- responsive`.

Arabic and Persian RTL tests also cover desktop/mobile mirroring, LTR technical inputs and code,
mixed Latin/Arabic text, keyboard dialog closure and focus restoration, saved-language
embed/reload, vertical reorder arrows, drag and drop, and switching back to LTR.
Run them with `npm run test:e2e -- rtl`. Persian uses `fa-IR-u-ca-gregory`
so collection dates retain the Gregorian calendar with Persian digits.

### Chromium visual comparisons

Install the development JavaScript tools as above, have Bash available, and
ensure Docker is running:

```bash
npm run test:visual
```

This command builds the production assets and runs `playwright.visual.config.js`
in the Linux/amd64 Playwright 1.55.0 Noble image pinned by digest in
`scripts/test_visual.sh`. Chromium, system fonts, rendering libraries, Node and
architecture come from that image. Keep its Playwright version aligned with
`package.json`. The browser container has no external network; the fixture server
and browser communicate over its loopback interface.

Eight Finnish cases cover 320, 430, 768 and 1280 CSS pixels in light and dark themes:
narrow and wide phones, tablet and desktop layouts. Touch input is enabled for
the phone and tablet widths; the desktop case uses mouse input. The intermediate
390-pixel phone layout remains covered by the functional responsive tests.
Each compares login, results, bin selection, feedback, reminders and compact embed:
72 reviewed PNG baselines in `tests/e2e/visual.spec.js-snapshots/`. Four additional Arabic cases cover RTL at 320 and 1280 pixels in both themes.
Arabic is the only RTL screenshot language; Persian has functional/layout checks
and adds no visual baselines.
The tests use Finnish or Arabic UI text, UTC, a fixed reference week (2024-01-01), device scale 1, reduced motion,
hidden carets, neutral focus and loaded fonts/images. Collection dates follow
that fixed week; ordinary functional tests still use the current week.

Functional E2E runs exclude the visual file, so Firefox never creates or compares
screenshots. CI runs visual comparisons twice, with no retries or automatic
baseline updates, and uploads expected/actual/diff images and traces on failure.
The pixel color-distance threshold is 0.1, with zero changed pixels allowed beyond
that threshold.

For an intentional UI change, generate new images in the same container:

```bash
npm run test:visual -- --update-snapshots
npm run test:visual -- --repeat-each=2
```

Inspect the updated PNGs and any differences before committing them with the
corresponding UI change. Updating the renderer image or fonts also requires
reviewing all affected images. Baselines from a host browser are not interchangeable
with the pinned container. `npm run test:visual:runner` is the internal container
command; use it directly only when debugging a different local environment.

The checked-in fixture is under `tests/fixtures/`. Never commit real customer numbers, passwords or personal API payloads as test fixtures.

## Manual fixture testing

For manual browser testing without upstream access, start Renyyt with a saved JSON response:

```bash
RENYYT_FIXTURE_FILE=tests/fixtures/e2e-services.json PYTHONPATH=src python3 -m renyyt
```

Alternatively, use the JSON import control in the UI's **Show HTTP request** dialog. Browser-side import does not upload the selected file to the Renyyt server.

`renyyt --check` validates a configured fixture before the server starts:

```bash
RENYYT_FIXTURE_FILE=tests/fixtures/e2e-services.json PYTHONPATH=src python3 -m renyyt --check
```

## Production and reproducible-build checks

Build production assets:

```bash
python3 scripts/build.py
```

Verify that the release archive and wheel are byte-for-byte reproducible when the same `SOURCE_DATE_EPOCH` is used:

```bash
python3 scripts/check_reproducible.py
```

Create a release archive manually with:

```bash
python3 scripts/package.py
```

## Configuration smoke check

Before running a deployment, validate configuration and required runtime files:

```bash
PYTHONPATH=src python3 -m renyyt --check
```

This also reports whether feedback SMTP, the memory cache and fixture mode are enabled.

## GitHub Actions CI

`.github/workflows/ci.yml` runs on pushes, pull requests and manual dispatches.
It contains five job definitions:

- **changes** — inspect the complete push or PR diff to decide whether browser tests are needed.
- **python** — Python 3.8 and 3.13 regression tests, compile checks and production builds. Python 3.13 also runs the installed-package smoke test, release packaging and reproducible-build verification.
- **quality** — Python 3.13 for Ruff, coverage and the fixture server; ESLint, frontend unit tests, JavaScript syntax checks and Playwright E2E tests on Chromium and Firefox.
- **container** — Python 3.13 Docker image build, runtime version/configuration,
  non-root user, readiness endpoint and graceful shutdown checks.
- **visual** — 72 Chromium screenshot comparisons in a pinned container, repeated twice.

Changes confined to `Dockerfile` and/or `.dockerignore` skip Playwright browser
installation, functional E2E and the visual job. Python tests, coverage, linting,
frontend helper tests, builds and container checks still run. This is a narrow
allowlist: server, UI, build, test, dependency, workflow, documentation and unknown
paths all keep browser coverage enabled. PRs compare their head with the merge base;
pushes compare the before/after commits across the entire push. Renames include
both old and new paths. A new branch's first push compares with the default branch's
merge base. Missing history, empty diffs and unrecognized events run all checks;
**Run workflow** is also available to force a full run.
CI selection regressions use synthetic Git repositories and require Git locally.

The tag-triggered release workflow also uses Python 3.13 for tests, builds and
packaging. The minimum supported Python version remains 3.8.

A failure in any required job makes the workflow fail. The quality tools are not runtime dependencies of Renyyt, but their CI failures should be fixed before release.

## Suggested pre-release command set

For a development machine with all tools installed:

```bash
ruff check src tests scripts run.py
PYTHONPATH=src coverage run --branch -m unittest discover -s tests -p 'test_*.py'
coverage report --fail-under=78
npm run lint:js
npm run test:frontend
npm run test:e2e
python3 scripts/build.py
python3 scripts/check_reproducible.py
PYTHONPATH=src python3 -m renyyt --check
```

## Web Push -muistutusten testaus

Reminder-storen, schedulerin ja API-synkronoinnin regressiot kuuluvat Python-testisarjaan. Varsinaista push-palveluun lähetystä ei CI:ssä tehdä ulkoiseen endpointiin; lähettäjä testataan mockatulla `pywebpush`-rajapinnalla. Paikallisessa integraatiotestissä push-extra asennetaan komennolla `pip install '.[push]'`, generoidaan VAPID-avaimet komennolla `renyyt reminders generate-vapid` ja `renyyt --check` varmistaa konfiguraation. Erääntyneet muistutukset voi ajaa käsin `renyyt reminders run-due` -komennolla ja storen tilanteen nähdä `renyyt reminders stats` -komennolla.

## Translation loading

`web/i18n.js` intentionally remains one synchronous, fingerprinted production asset.
Six complete dictionaries occupy about 89 kB uncompressed / 22 kB with gzip.
Compression is provided by the reverse proxy or an explicit `build.py --gzip`;
the Python server does not compress responses dynamically. Language switching
needs no additional fetch and works with the cached offline shell. At this size,
per-language lazy loading adds more network/offline states than its transfer savings
justify. Per-language source files bundled at build time remain a maintenance option
if the dictionary becomes hard to edit; that does not require a new runtime loader.

To add a language, translate all dictionary keys (currently 210), preserve named
placeholders, register its locale/direction and add a language-selector option and
native language name in every dictionary. Extend functional language, date/number,
embed/persistence and responsive checks on Chromium and Firefox. Screenshot
languages are chosen separately; Finnish represents LTR and Arabic represents RTL.

Vietnamese can use `vi` / `vi-VN` with LTR layout; check font coverage and clipping
of its stacked diacritics. Chinese also uses LTR layout, but first choose Simplified
(`zh-Hans`) or Traditional (`zh-Hant`) and the intended regional locale, such as
`zh-CN` or `zh-TW`. Verify CJK font fallback, punctuation and line breaking without
spaces, plus IME composition in editable text. These additions need no new Python
API or runtime dependency; language selection does not change the EUR currency.
