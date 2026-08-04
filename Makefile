.PHONY: install browsers lint test test-e2e ci demo

install:
	uv sync --extra test

browsers:
	uv run playwright install chromium

lint:
	uv run ruff check .

test:
	uv run pytest tests/unit tests/api

test-e2e:
	uv run pytest tests/e2e -m "smoke or regression" --browser chromium --tracing retain-on-failure --screenshot only-on-failure --video retain-on-failure --output test-results

ci: lint test test-e2e

demo:
	uv run uvicorn examples.demo_app.main:app --host 0.0.0.0 --port 8000
