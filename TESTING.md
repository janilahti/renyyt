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

Install Chromium for Playwright once:

```bash
npx playwright install --with-deps chromium
```

Then run the browser suite:

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
starts its own fixture server and uploads browser failure traces.

Chromium is the current baseline. The next phase in [ROADMAP.md](ROADMAP.md) adds
Firefox functional coverage and dedicated responsive/Chromium visual regressions
after the full GitHub Actions baseline is green.

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

`.github/workflows/ci.yml` runs on pushes and pull requests. It contains three jobs:

- **python** — Python 3.8/3.11/3.13 regression tests, compile checks, production build, installed-package smoke test, release packaging and reproducible-build verification.
- **quality** — Ruff, coverage, ESLint, frontend unit tests, JavaScript syntax checks and Playwright/Chromium E2E tests.
- **container** — Docker image build.

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
