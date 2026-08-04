# Failure classification

- Product defect: stable behavior contradicts a confirmed requirement and is reproducible below the UI layer.
- Test defect: locator, fixture, synchronization, cleanup, or assertion implementation is wrong.
- Environment defect: service, network, browser lifecycle, dependency, or deployment is unavailable.
- Test data defect: data collides, violates constraints, or is stale.
- Flaky: unchanged code and environment produce inconsistent outcomes.
- Requirement conflict: expected behavior is ambiguous or contradictory.
- Unknown: evidence is insufficient; do not auto-edit tests.
