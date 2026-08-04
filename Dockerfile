FROM mcr.microsoft.com/playwright/python:v1.57.0-noble

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY examples ./examples
COPY config ./config
COPY targets ./targets
COPY proofs ./proofs
COPY experiments ./experiments
COPY tests ./tests
COPY docs ./docs
COPY .agent ./.agent

RUN pip install --no-cache-dir . \
    && mkdir -p /app/test-results /app/.target-work \
    && chown -R pwuser:pwuser /app

USER pwuser

ENTRYPOINT ["test-workflow"]
CMD ["--help"]
