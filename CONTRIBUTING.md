# Contributing

## Development

Read [AGENTS.md](AGENTS.md) for engineering boundaries and [ROADMAP.md](ROADMAP.md)
for ordered priorities. Until explicitly changed, version bumps change only the
patch component; CI/test maintenance does not automatically require a release.

Requirements: Python 3.8+ and Node.js for the small frontend test suite. The application itself has no Node runtime dependency.

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
node tests/test_frontend.js
python3 scripts/build.py
python3 run.py
```

Before submitting a change:

1. add or update regression tests for changed behavior;
2. run the complete Python and frontend test suites;
3. run the production build;
4. do not commit generated `dist/` files unless a release process explicitly requires them;
5. never include customer numbers, passwords, API payloads or other personal data in tests, logs or issues.

## Code style

Keep the runtime dependency-free unless there is a concrete reason to add a dependency. Preserve Python 3.8 compatibility. Prefer small modules with focused responsibilities.

## Security issues

Do not open a public issue for a vulnerability that could expose credentials or customer data. See `SECURITY.md`.
