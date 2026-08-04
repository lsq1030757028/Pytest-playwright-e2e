FROM mcr.microsoft.com/playwright/python:v1.57.0-noble

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY examples ./examples
COPY tests ./tests
COPY config ./config

RUN pip install --no-cache-dir -e '.[test]'

CMD ["pytest", "tests", "--browser", "chromium", "--tracing", "retain-on-failure", "--screenshot", "only-on-failure", "--video", "retain-on-failure", "--output", "test-results", "--junitxml", "test-results/junit.xml"]
