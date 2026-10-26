# Security policy

Renyyt handles credentials and customer-specific waste-service data. Never put real
credentials, customer numbers, addresses, API payloads, subscription keys or
credential-bearing embed URLs in public issues, fixtures or logs attached to reports.

## Reporting

Use GitHub's private vulnerability reporting if it is enabled for this repository.
If that option is unavailable, arrange a private channel with the repository owner
before sharing details. Do not open a public vulnerability issue containing sensitive
information. This policy does not claim that a private reporting channel is configured.

## Dependency monitoring

[Dependabot configuration](.github/dependabot.yml) checks Python (`pyproject.toml`,
including optional extras), npm development dependencies, GitHub Actions and the
Dockerfile base image weekly on Mondays at 07:00 Europe/Helsinki. The schedule
is GitHub's target start time, not a delivery guarantee. Updates begin after the
configuration reaches the default branch. Minor/patch version updates are grouped
per ecosystem, major updates remain separate, and each ecosystem has at most
three open version-update PRs. No auto-merge is configured and no versions or
advisories are ignored.

Version updates are separate from **Dependabot alerts** and **Dependabot security
updates**. The owner should open [repository security settings](https://github.com/janilahti/renyyt/settings/security_analysis)
(Settings → Security → Advanced Security; some GitHub interfaces call this
Code security) and check that the dependency graph, Dependabot alerts and
Dependabot security updates are enabled. Alerts compare GitHub's dependency graph
against known advisories; security updates can open fix PRs outside the weekly
version-update schedule. The version-update PR limit does not limit security
update PRs. On 2026-10-26, the dependency graph was verified by exporting the
repository SBOM, and GraphQL confirmed `hasVulnerabilityAlertsEnabled: true`
with zero open vulnerability alerts. This is a point-in-time check, not a claim
that all deployed or transitive components are vulnerability-free. The REST
administrative read API for Dependabot security updates still returns HTTP 403
to the integration, so that separate toggle needs owner confirmation. No extra
repository Actions secret is needed for these public dependency sources.

There are no committed npm/Python lockfiles. Monitoring sees the declared manifests;
this does not guarantee a complete inventory of every transitive dependency or the
exact versions used by a particular deployment. Base Renyyt has no external Python
runtime dependencies; optional Web Push and development/build tools still need
review. Dependencies installed by the distribution package manager remain the
operator's responsibility.

Docker version updates are not a container vulnerability scan. A floating base tag
such as `python:3.13-slim` may receive security fixes without a tag-name change;
rebuild and redeploy images to consume them. Dependabot does not refresh published
GHCR images or native Release assets automatically. The Playwright renderer image
pinned inside `scripts/test_visual.sh` also needs manual review; the Docker updater
here watches the root Dockerfile, not image strings embedded in shell scripts.

Review and run CI before merging. Preserve Python 3.8 compatibility and optional
Web Push environment markers. A Playwright update must also align the version and
reviewed image digest in `scripts/test_visual.sh`; review visual changes and update
baselines only deliberately. Changes to Python base-image versions must agree with
the container checks. Dependabot PRs run without repository Actions secrets; keep
production signing/publishing in the existing trusted release workflows. This
setup does not add a `pull_request_target` workflow or bypass required checks.

## Credentials and browser storage

Users sign in with their own Renyy Oma jätehuolto credentials; Renyyt has no
separate user accounts. The UI includes a short data-minimisation/storage notice
in every supported language. It describes application behavior rather than
certifying GDPR compliance for an operator's deployment. Operators must account
for their own logging, retention and optional-service configuration when providing
deployment-specific privacy information.

The Python server does not persist Renyy credentials. It handles them in memory while
proxying a request. Browser credential storage is opt-in: AES-GCM obscures a blob but
the key travels alongside it, so this is **not secure encryption** against local
browser access or XSS. Credential-bearing embed fragments have the same limitation.
Fragments are not sent with the HTTP GET, but the whole URL must be kept secret.
The page sends the decoded credentials to the configured Renyyt API when fetching data.

The browser also stores view settings and a reduced collection snapshot for stale-data
fallback. That snapshot excludes the full raw response and shareholder detail structures,
but still contains customer-specific collection information. Avoid shared devices.

## Logs and process memory

INFO/DEBUG omit credentials and request/response bodies. TRACE is an explicitly
sensitive diagnostic exception: it can include API credentials and parsed JSON, SMTP
credentials, feedback content and SMTP protocol replies. Upstream HTML/JavaScript
is not logged, even at TRACE. Enable TRACE only temporarily, restrict log access and
remove the logs afterwards. Never copy unredacted TRACE output into an issue.

The optional TTL/LRU response cache is disabled by default. It stores customer JSON
in process RAM, with per-process HMAC request keys. A previously valid credential pair
can still receive a cached response until TTL expiry after upstream password changes.
Use a short TTL or disable caching where immediate revocation is required.

## Feedback and Web Push

Collection-data feedback attachments require an explicit user choice and can contain
customer data. The application does not add the login password; it relays the attachment
via SMTP without storing it on disk. Caller-provided arbitrary JSON must still be
reviewed before sharing.

Reminder SQLite data includes capability-like push endpoints, subscription keys,
collection dates and labels, but no Renyy login credentials. Protect the DB, its
WAL/SHM files, backups and VAPID private key. Standard database filenames are excluded
from Git, Docker context and source archives, but ignore rules cannot recognize every
secret: keep private files outside the source tree. Reminder sends use the last
browser-supplied snapshot; the server cannot refresh upstream dates independently.

## Deployment boundary

Use HTTPS outside localhost, keep the backend private behind the proxy, and trust only
actual proxy IPs/CIDRs. Preserve Host/Origin validation, request limits, rate limits and
CSP. Metrics contain no customer labels but may expose operational information; restrict
them at the proxy if needed. Embedding is intentional: frame restrictions are not added
by default. Multi-instance rate limits/cache are per process, not a global protection.
See [TECHNICAL.md](TECHNICAL.md) for configuration and deployment examples.
