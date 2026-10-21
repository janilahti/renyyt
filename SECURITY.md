# Security policy

Renyyt handles credentials and customer-specific waste-service data. Never put real
credentials, customer numbers, addresses, API payloads, subscription keys or
credential-bearing embed URLs in public issues, fixtures or logs attached to reports.

## Reporting

Use GitHub's private vulnerability reporting if it is enabled for this repository.
If that option is unavailable, arrange a private channel with the repository owner
before sharing details. Do not open a public vulnerability issue containing sensitive
information. This policy does not claim that a private reporting channel is configured.

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
