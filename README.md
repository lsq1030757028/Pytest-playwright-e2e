# Pytest + Skill + Playwright Test Workflow

> **Project status:** `FOUNDATION_BASELINE`  
> The v0.1 Harness microkernel and trustworthy execution baseline are merged and released. The project is **not yet a stage-deliverable Test Agent Runtime**. The next roadmap is Memory & Controlled Self-Evolution → Cross-model Generalization → Project / Architecture Generalization. See `docs/agent-os-evolution-roadmap.md` and `docs/implementation-status.md`.

A production-oriented test workflow that separates responsibilities clearly:

- **Skill** controls test decisions, guardrails, evidence requirements, and failure handling.
- **Pytest** handles fixtures, parametrization, markers, execution, and reporting.
- **Playwright** handles browser interactions, semantic locators, auto-waiting, traces, screenshots, and videos through a repository-owned Pytest plugin.
- **Quality gates** turn execution data into `PASS`, `PASS_WITH_RISK`, `FAIL`, or `BLOCKED`.

The repository includes a runnable demo application. Browser smoke tests use the real page with a controlled API double, while CI also runs a live browser-to-service integration test.

## Architecture

```text
Requirement / PR
      ↓
Web Test Workflow Skill
      ↓
Preflight → Risk model → Existing capability scan
      ↓
Pytest collection → API tests → Playwright smoke/regression
      ↓
Trace / screenshot / console / failed network requests
      ↓
Failure classification → Repair or defect report
      ↓
Quality gate and Markdown/JUnit reports
```

The internal architecture is evolving toward a domain-specific Agent OS microkernel:

```text
Capability Atoms
+ Versioned Artifacts
+ Harness Orchestrator
+ Dynamic Execution DAG
+ Progressive Context / Memory
+ Policy / Budget / Permission
```

## GitHub development SSOT

All human and Agent development follows one cloud-first GitHub process:

```text
Goal / Issue
→ risk and impact triage
→ branch
→ change-specific evidence plan
→ implementation
→ Pull Request and GitHub Actions
→ review and merge
→ main / release verification
→ status, asset, and branch closure
```

Start with `AGENTS.md`. The normative process is `docs/github-development-ssot.md`, and its machine-readable policy is `docs/github-development-ssot.yaml`.

Testing is risk-adaptive rather than a fixed “unit test + integration test for every module” checklist. Each change selects the cheapest trustworthy evidence for its actual business and technical boundaries; the repository-wide GitHub Actions suite remains the regression and release-protection baseline.

## Quick start

```bash
uv sync --extra test
uv run playwright install chromium
uv run pytest tests/unit tests/api
uv run pytest tests/e2e -m "smoke or regression" --browser chromium \
  --tracing retain-on-failure \
  --screenshot only-on-failure \
  --video retain-on-failure \
  --output test-results
```

Run the workflow CLI:

```bash
uv run test-workflow preflight --config config/local.yaml
uv run test-workflow run --config config/local.yaml --marker smoke --browser chromium
uv run test-workflow report test-results/junit.xml --output test-results/report.md
```

Run the demo app manually:

```bash
uv run uvicorn examples.demo_app.main:app --host 0.0.0.0 --port 8000
```

Then open `http://localhost:8000`.

## Repository layout

```text
AGENTS.md                         Mandatory Agent development entrypoint
.agent/skills/web-test-workflow/  Agent Skill and test policies
src/test_workflow/                Workflow CLI and reusable engine
examples/demo_app/                Runnable target application
config/                           Environment configuration
docs/github-development-ssot.*   GitHub cloud development process SSOT
tests/unit/                       Workflow unit tests
tests/api/                        Service-level tests
tests/e2e/                        Playwright pages, flows, and specs
.github/workflows/                CI and deployment validation
```

## Safety model

- Production is read-only unless explicitly approved.
- A failed assertion is never changed merely to make CI green.
- Every failure is classified with evidence.
- Browser E2E tests cover critical workflows; combinatorial rules stay at unit/API level.
- Fixed sleeps and brittle layout selectors are rejected by policy.
- Models propose candidates; deterministic policies control Oracle, permissions, promotion, and release gates.
- Future memory and self-evolution assets must be versioned, benchmarked, reversible, and isolated from confirmed truth.

## Deployment

The repository ships a test-runner image, a demo-service image, Docker Compose, GHCR publishing, and a Kubernetes manifest. See `deploy/README.md`.

## Docker

```bash
docker compose up --build demo-app
```

The demo app is exposed at `http://localhost:8000`. The CI image can run the full Playwright suite with:

```bash
docker compose run --rm test-runner
```

## Deterministic environment and mocks

The workflow now treats the test environment as a compiled artifact:

- `TestSpec` defines requirements, risks, Oracles, and the truth boundary.
- `EnvironmentSpec` fixes time, randomness, storage, real services, and virtual services.
- `MockPlan` prevents mocks from replacing the business behavior under test.
- contract-backed virtual services validate response schemas before execution.
- `ReplayManifest` pins every input with SHA-256 for independent replay.

Runnable example:

```bash
uv run test-workflow mock verify experiments/todomvc-golden-loop
uv run test-workflow env build experiments/todomvc-golden-loop
uv run test-workflow bundle validate experiments/todomvc-golden-loop
uv run test-workflow replay experiments/todomvc-golden-loop
```

See `docs/mock-control-plane.md` for the truth-boundary and environment-control design.
