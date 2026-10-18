# Contributing

Read [AGENTS.md](AGENTS.md) for engineering rules, [ROADMAP.md](ROADMAP.md) for
completed gates and next work, and [TESTING.md](TESTING.md) for exact validation commands.
Version bumps remain patch-only when needed; maintenance does not imply a release.

## Development

Runtime: Python 3.8+, no external dependencies for the base application. Development:
Python 3.13 and Node.js 24 recommended. Push dependencies are an optional extra.

```bash
python3 -m venv .venv
. .venv/bin/activate
python scripts/build.py
python -m pip install -e '.[dev]'
npm install
python -m unittest discover -s tests -p 'test_*.py'
npm run test:frontend
python run.py
```

Add meaningful regressions for behavior changes. Run Python/frontend checks, build,
lint/coverage and applicable browser tests before submitting code changes. Visual
baselines must be reviewed and generated in the pinned renderer, never blindly updated.
Markdown-only changes use the lightweight documentation checks in TESTING; workflow,
configuration and mixed changes still need broader checks.

Do not commit `dist/`, caches, package artifacts, SQLite databases, secrets or personal
API payloads. Use synthetic fixture data and relative/frozen dates. Every new UI string
must exist in all supported dictionaries; preserve placeholders, RTL and accessibility.
Keep the runtime dependency-light, CSP strict, and Python 3.8 compatible.

Do not publish sensitive vulnerabilities in issues. See [SECURITY.md](SECURITY.md).
