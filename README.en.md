# Renyyt – quick guide

Renyyt shows upcoming waste-bin collections from Renyy’s (Pirkanmaan Jätehuolto) Oma jätehuolto service. It is an unofficial client.

Service: <https://renyyt.fi/>. To self-host, use Python 3.8 or newer: extract a release archive, run `python3 run.py` in its directory and open <http://127.0.0.1:8787>.

## Basic use

1. Choose a language, enter your Oma jätehuolto customer number and password, and select **Fetch collections**.
2. **Bins** selects the visible bins. **Order → Custom order** enables arrows or dragging in normal view. **Compact view** keeps that order without editing controls.
3. Export the next collections as an `.ics` calendar. **Embedded view** shows collections only. Installation, feedback and reminders depend on server settings and browser support.

Saving credentials is optional. The browser’s credential blob is not secure encryption; avoid saving on shared devices and keep credential-bearing embed links secret. Reminders use the last successful browser fetch. Saved fallback data is marked stale.

More: [full guide (Finnish)](README.md), [setup and settings (Finnish)](TECHNICAL.md), [API (Finnish)](API.md), [changes (English)](CHANGELOG.md), [testing (English)](https://github.com/janilahti/renyyt/blob/main/TESTING.md).
