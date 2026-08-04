# Contributing

1. Create a focused branch.
2. Add or update the requirement-to-test mapping.
3. Run `uv run ruff check .`.
4. Run `uv run pytest --collect-only`.
5. Run unit/API tests before browser tests.
6. Retain Playwright evidence for failures.
7. Do not weaken assertions without confirmed requirement evidence.
