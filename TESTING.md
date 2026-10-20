# Testing Renyyt

This document collects the project's local development and CI test commands in one place.
The application itself has no runtime dependency on Node.js, Playwright, Ruff, ESLint or coverage.py; those tools are development and CI dependencies only.

## Prerequisites

- Python 3.8 or newer
- Node.js 24 recommended (also used in CI) for the JavaScript quality and browser test suite
- A normal network connection when installing development dependencies or Playwright browsers

Create a Python virtual environment and install the development extras:

```bash
python3 -m venv .venv
. .venv/bin/activate
python scripts/build.py
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

Install Chromium, Firefox and WebKit for Playwright once:

```bash
npx playwright install --with-deps chromium firefox webkit
```

Build the current production assets before running the suite; a stale partial `dist/`
causes readiness to fail. Then run all three browsers:

```bash
python3 scripts/build.py
npm run test:e2e
```

The E2E suite starts the real Renyyt HTTP server and uses `RENYYT_FIXTURE_FILE` instead of the external Oma jätehuolto service. This means the browser, HTTP API, validation and rendering paths are tested together without requiring real credentials or an external network dependency.

Browser tests freeze the clock at the current week's Monday in UTC and adjust only
the fixture response's collection dates relative to that day. Date-label assertions
therefore do not expire or depend on the runner's timezone. The tests cover saved
credentials, translations, drag handles and move buttons, saved-credential embed
links, portable credential/view links in a fresh browser context, documentation
links, install UI, normal-view ordering controls, compact-order persistence and the offline service-worker shell. CI always
starts its own fixture server and uploads browser failure traces. The offline-shell
case removes the unused API date interception because routing disables Firefox's
cache and bypasses its service worker on reload. It verifies the response was
served by the service worker while the browser is offline.

CI and release workflows use Ubuntu 24.04 and Node.js 24. Runner OS upgrades are
explicit changes so browser and build dependencies do not move with `ubuntu-latest`.

Playwright WebKit provides a Safari-engine compatibility signal on Linux; it
does not run the shipping macOS/iOS Safari application. Real Safari/PWA install,
OS sharing and push behavior still need device testing.

All functional E2E tests run on Chromium, Firefox and WebKit locally and in CI. To run
just one browser, use `npm run test:e2e -- --project=firefox` (or `chromium` / `webkit`).
Responsive tests run on all three browsers at widths of 320, 390 and 430 CSS
pixels, with touch input enabled. They check horizontal overflow, overlapping
controls, header/card/dialog content, selected option text, saved-credential
help layout and 44-by-44 CSS-pixel touch targets (native
checkboxes use their labels). Header and login checks cover all nine UI languages;
results, manual ordering, bin selection and feedback/reminder dialogs cover
Finnish, Ukrainian, Arabic, Persian, Vietnamese, Simplified Chinese and Estonian. Compact embed is also checked at each width. Dialog tests
exercise touch operation and focus restoration. Optional feature flags are mocked; feedback and reminder
writes are blocked and fail the test if attempted.

Run only these checks with `npm run test:e2e -- responsive`.

Arabic and Persian RTL tests also cover desktop/mobile mirroring, LTR technical inputs and code,
mixed Latin/Arabic text, keyboard dialog closure and focus restoration, saved-language
embed/reload, vertical reorder arrows, drag and drop, and switching back to LTR.
Run them with `npm run test:e2e -- rtl`. Persian uses `fa-IR-u-ca-gregory`
so collection dates retain the Gregorian calendar with Persian digits.

Vietnamese (`vi`, `vi-VN`), Simplified Chinese (`zh-Hans`, `zh-CN`) and Estonian
(`et`, `et-EE`) also have
functional layout checks at 768/1280px for login, results, dialogs and embed.
They verify localized dates, saved language, Unicode feedback input and IME Enter
handling. IME regressions synthesize composition key events to check application
submission behavior; they do not emulate an operating-system candidate window.
Run these cases with `npm run test:e2e -- languages`.
Only Finnish and Arabic have screenshot baselines.


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
Each compares login, results, bin selection, feedback, reminders and compact embed.
Four additional Arabic cases cover RTL at 320 and 1280 pixels in both themes.
Together these use 72 reviewed PNG baselines in `tests/e2e/visual.spec.js-snapshots/`.
Arabic is the only RTL screenshot language; Persian has functional/layout checks
and adds no visual baselines.
The tests use Finnish or Arabic UI text, UTC, a fixed reference week (2024-01-01), device scale 1, reduced motion,
hidden carets, neutral focus and loaded fonts/images. Collection dates follow
that fixed week; ordinary functional tests still use the current week.

Functional E2E runs exclude the visual file, so Firefox and WebKit never create or compares
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

Verify that the release tar.gz/ZIP archives and wheel are byte-for-byte reproducible when the same `SOURCE_DATE_EPOCH` is used:

```bash
python3 scripts/check_reproducible.py
```

Create a release archive manually with:

```bash
python3 scripts/package.py --format all
```

## Configuration smoke check

Before running a deployment, validate configuration and required runtime files:

```bash
PYTHONPATH=src python3 -m renyyt --check
```

This also reports whether feedback SMTP, the memory cache and fixture mode are enabled.

## GitHub Actions CI

`.github/workflows/ci.yml` runs on pushes, pull requests and manual dispatches.
The checks are selected from the complete diff:

| Change | Checks |
| --- | --- |
| Only `*.md` files, including nested docs and `.github` instructions | CI-selection/documentation regressions, Markdown file-link and `.env.example` name checks, production build and `--check`; no Python matrix, coverage, npm/browser install, E2E, Docker or visual tests |
| Only `Dockerfile`/`.dockerignore`, optionally with Markdown | Full Python/quality/build/container checks; no browser install, E2E or visual job |
| Application, workflow, tests, dependency/configuration or unknown paths | All checks |
| Manual run, malformed event, missing history or empty diff | All checks |

Job definitions:

- **changes** — select `full` and `browser` outputs conservatively.
- **documentation** — run the lightweight checks on every revision; this is the substantive gate on Markdown-only changes.
- **python** — Python 3.8/3.13 regressions, compile and production build; 3.13 also checks the installed package, source archive and reproducibility.
- **quality** — Ruff, branch coverage (78%), ESLint, frontend helpers and syntax; Chromium/Firefox/WebKit E2E when browser checks are enabled.
- **container** — Python 3.13 image, non-root runtime, excluded SQLite data, actual healthcheck with default/custom port and base path, graceful shutdown.
- **visual** — 72 pinned Chromium comparisons, repeated twice.

PRs compare their whole head against the merge base; pushes compare before/after
across the entire push. A Markdown-only last commit does not hide earlier code in
a PR. A new branch's first push compares against the default branch. Renames include
both old and new paths, so renaming code to Markdown still runs the full suite.
**Run workflow** forces a full run. There are no workflow-level path exclusions that
could leave a required workflow perpetually pending. Job-level skips are deliberate; `changes` and `documentation` still report a result
for Markdown-only revisions.

Run the lightweight checks locally:

```bash
python3 -m unittest discover -s tests -p 'test_ci_browser_changes.py'
python3 -m unittest discover -s tests -p 'test_documentation.py'
python3 scripts/check_docs.py
python3 scripts/build.py
python3 run.py --check
```

The link checker validates local file targets and rejects relative Markdown links
from in-app documents to routes the server does not serve (use repository URLs for
those files). It does not check remote website availability or heading anchors. CI-selection regressions use synthetic Git history.
Changes to `.env.example`, deploy unit/config files or workflows are not Markdown-only.

The tag-triggered release workflow also uses Python 3.13 for tests, builds and
packaging. The minimum supported Python version remains 3.8.

The release workflow is a smaller final smoke check; verify full green CI for the exact commit before tagging, following `.github/release-checklist.md`.

A failure in any required job makes the workflow fail. The quality tools are not runtime dependencies of Renyyt, but their CI failures should be fixed before release.

## Suggested pre-release command set

For a development machine with all tools installed:

```bash
ruff check src tests scripts run.py
PYTHONPATH=src coverage run --branch -m unittest discover -s tests -p 'test_*.py'
coverage report --fail-under=78
npm run lint:js
npm run test:frontend
python3 scripts/build.py
npm run test:e2e
npm run test:visual -- --repeat-each=2
python3 scripts/check_reproducible.py
PYTHONPATH=src python3 -m renyyt --check
```

## Web Push -muistutusten testaus

Reminder-storen, schedulerin ja API-synkronoinnin regressiot kuuluvat Python-testisarjaan. Varsinaista push-palveluun lähetystä ei CI:ssä tehdä ulkoiseen endpointiin; lähettäjä testataan mockatulla `pywebpush`-rajapinnalla. Paikallisessa integraatiotestissä push-extra asennetaan komennolla `pip install '.[push]'`, generoidaan VAPID-avaimet komennolla `renyyt reminders generate-vapid` ja `renyyt --check` varmistaa konfiguraation. Erääntyneet muistutukset voi ajaa käsin `renyyt reminders run-due` -komennolla ja storen tilanteen nähdä `renyyt reminders stats` -komennolla.

## Translation loading

`web/i18n.js` intentionally remains one synchronous, fingerprinted production asset.
Nine complete dictionaries are bundled in that asset.
Compression is provided by the reverse proxy or an explicit `build.py --gzip`;
the Python server does not compress responses dynamically. Language switching
needs no additional fetch and works with the cached offline shell. At this size,
per-language lazy loading adds more network/offline states than its transfer savings
justify. Per-language source files bundled at build time remain a maintenance option
if the dictionary becomes hard to edit; that does not require a new runtime loader.

To add a language, translate all dictionary keys (currently 213), preserve named
placeholders, register its locale/direction and add a language-selector option and
native language name in every dictionary. Extend functional language, date/number,
embed/persistence and responsive checks on Chromium, Firefox and WebKit. Screenshot
languages are chosen separately; Finnish represents LTR and Arabic represents RTL.

Vietnamese uses `vi` / `vi-VN` with LTR layout; check font coverage and clipping
of its stacked diacritics. The implemented Chinese choice is Simplified (`zh-Hans`, `zh-CN`) with LTR layout.
A future Traditional variant would use its own language/locale choice, such as
`zh-Hant` / `zh-TW`. Verify CJK font fallback, punctuation and line breaking without
spaces, plus IME composition in editable text. These additions need no new Python
API or runtime dependency; language selection does not change the EUR currency.

## Localized guides and release archives

The README button opens `README.<language>.md` for each supported UI language.
Browser tests verify all nine guides and RTL direction, and links back to the Finnish
technical guide restore LTR. Python tests cover GET/HEAD/OPTIONS, validators, base paths
and missing-guide readiness. Wheel data and both archive formats include every guide.

`package.py --format all` uses the same exclusions for tar.gz and ZIP. ZIP timestamps
are UTC and clamped to DOS's 1980–2107 range; `SOURCE_DATE_EPOCH` makes both formats
reproducible. Regression tests compare payload bytes, private/generated-file exclusion,
permissions and fixed-epoch repeatability. Release CI publishes both archives and
`SHA256SUMS`; CI does not publish images from pull requests. Tagged releases publish native Linux packages and then invoke the OCI/GHCR workflow.

## Native Linux packages

`python3 scripts/package_linux.py --format all` requires `dpkg-deb` and `rpmbuild`. Outputs are architecture-independent deb/rpm base packages under `build/linux`; `--revision 2` creates an upgrade fixture without an application-version change. Fix `SOURCE_DATE_EPOCH` and the build toolchain to compare bytes. Native CI builds twice and compares both packages byte for byte.

The reusable `native-packages.yml` workflow runs only for full CI and tagged releases. It checks actual systemd startup, running-service upgrade, stopped/disabled-service preservation, ordinary remove and purge on a disposable Ubuntu runner. Disposable Debian 12/13, Ubuntu 22.04/24.04, Fedora 44 and Rocky Linux 9/10 containers check payload permissions, non-root HTTP readiness, all localized guides, upgrades, retained configuration/data, unchanged RPM configuration, shell cleanup, and purge while installed. Rocky Linux provides a RHEL compatibility signal; it is not a claim of testing Red Hat subscription images. Containers do not run systemd as PID 1.

`tests/test_linux_packages.py` exercises ownership records, unsafe paths, account replacement and preservation without modifying the host. `scripts/test_linux_packages.py --disposable ...` performs destructive real installations and must run only in disposable containers/CI VMs, never on a workstation or production server.

Native distribution jobs also inspect the actual installed `Suggests` metadata and query `python3-pywebpush` availability. When supplied by the enabled repositories, they install it and exercise real VAPID key generation without sending notifications or printing keys. Missing optional packages do not block base-package installation; setup instructions document an isolated-venv fallback. The real systemd job installs the optional library in that isolated environment and tests the documented ExecStart override with ephemeral VAPID keys and the internal scheduler enabled.

Purge safety checks cover changed UIDs/GIDs before any cleanup, nested symlinks, configuration symlink targets, extra administrator files, pre-existing service users/groups, and unrelated `/opt/renyyt` and custom-data sentinels. Actual distribution jobs exercise both retained shell cleanup without Python and installed-package Python purge. The optional venv lives at `/opt/renyyt/venv`; package purge never recursively deletes `/opt/renyyt`.

The container CI validates an actual OCI archive with `scripts/check_oci.py` and
retains Docker readiness/port/base-path/non-root/shutdown checks. Publication uses
an existing stable release, checks tag/VERSION and immutable source SHA, and skips
moving latest during historical backfills. GHCR write credentials are only used
in publication, not PR checks.
Native jobs upgrade the released 1.0.0 deb/rpm to revision 2 of the candidate,
checking migration to /etc/renyyt.env, preservation of the explicit 8787 port and
subsequent purge. The real systemd job also starts the migrated service on that
retained port. Fresh-install runtime checks use 18514.
