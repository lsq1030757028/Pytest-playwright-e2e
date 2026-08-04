---
name: web-test-workflow
description: >
  Design, implement, execute, diagnose, and report Python web tests using Pytest
  and Playwright. Use for test planning, regression testing, PR validation,
  browser automation, failure analysis, and quality-gate decisions.
---

# Goal

Produce reliable tests and evidence-based conclusions.

Never modify an expected result merely to make a failing test pass.

# Required inputs

Resolve or derive:

- target feature or requirement
- environment
- allowed write operations
- test scope and risk
- browser matrix
- account and permission requirements

Production is read-only unless explicit approval is represented outside this Skill.

# Workflow

## 1. Preflight

Run `test-workflow preflight` and validate:

- environment configuration
- target health endpoint
- artifact directory
- browser availability
- account or secret availability when required
- write-operation policy

Stop with `BLOCKED` when preflight fails.

## 2. Model requirements and risk

Create a concise requirement-to-test matrix covering:

- positive behavior
- negative behavior
- boundary behavior
- permissions
- state transitions
- recovery behavior

Put combinatorial business rules in unit/API tests. Reserve browser E2E tests for critical user workflows.

## 3. Inspect existing capabilities

Before generating code, inspect:

- `tests/conftest.py`
- fixtures and data factories
- existing page and flow objects
- registered markers
- tests mapped to the same requirement

Prefer extending existing abstractions over creating duplicates.

## 4. Implement

Rules:

- tests are independent and deterministic
- create data through APIs when practical
- use semantic locators first: role, label, text, then stable test IDs
- never use fixed sleeps for synchronization
- use Playwright `expect` assertions
- every test contains a meaningful business assertion
- clean up created data
- do not swallow failures with broad exception handling

## 5. Validate test code

Run in order:

1. `ruff check .`
2. `pytest --collect-only`
3. unit and API tests
4. Chromium smoke tests
5. selected regression tests

Reject:

- `time.sleep` in E2E test code
- arbitrary layout-dependent XPath or CSS
- undocumented `force=True`
- unknown markers
- removed assertions without requirement evidence
- production writes

## 6. Capture evidence

On failure retain:

- Playwright trace
- screenshot
- video when enabled
- browser console
- failed network requests
- Pytest traceback
- environment metadata

## 7. Classify

Every failure is one of:

- `product_defect`
- `test_defect`
- `environment_defect`
- `test_data_defect`
- `flaky`
- `requirement_conflict`
- `unknown`

Provide the evidence and confidence. Do not change application assertions for product defects or requirement conflicts.

## 8. Repair and revalidate

Automatic test repair is allowed for supported test defects only, such as obsolete locators, fixture misuse, data collisions, missing Playwright synchronization, or cleanup defects.

After a repair:

1. show the diff
2. rerun the failed test
3. rerun the related module
4. rerun smoke tests

## 9. Report

Produce:

- scope and risk
- requirement coverage
- commands executed
- result counts
- failure classifications
- evidence paths
- changed files
- unresolved risks
- final gate: `PASS`, `PASS_WITH_RISK`, `FAIL`, or `BLOCKED`
