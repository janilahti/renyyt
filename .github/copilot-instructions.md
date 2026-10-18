# Copilot instructions for Renyyt

Follow [AGENTS.md](../AGENTS.md) as the canonical engineering guide and
[ROADMAP.md](../ROADMAP.md) for completed gates and next work. Use patch-only
version bumps when a release is needed; maintenance does not imply a version bump.

- Preserve Python 3.8+ and the dependency-light base runtime; push dependencies remain optional.
- Never commit or expose credentials/customer data. INFO/DEBUG must be safe; sensitive TRACE is an explicitly documented diagnostic exception, never a default.
- Keep CSP strict, the server free of persisted upstream credentials, and Host/Origin/proxy/request-limit protections intact.
- Preserve base paths, embed portability, PWA, Prometheus/OpenMetrics and accessibility.
- Translate new strings in all supported languages, preserve RTL and keep Finnish/Arabic as the chosen screenshot languages.
- Manual ordering is editable only in normal view; compact/embed preserve order without controls or dragging.
- Keep frontend sources in `web/`, generated assets in `dist/`; do not commit caches, packages or runtime SQLite files.
- Use meaningful regressions and the applicable checks in [TESTING.md](../TESTING.md). Markdown-only work uses lightweight CI; code/config/workflow/mixed changes require broader checks. Manual CI forces the full suite.
- Keep README concise and link technical detail; update docs and CHANGELOG with user/operator behavior.
- Release archives are `renyyt-<version>.tar.gz` with a top-level `renyyt/` directory. Verify full green CI for the exact commit before tagging.
