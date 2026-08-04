# Testing standards

1. Test behavior, not implementation details.
2. Keep business combinations at unit/API level.
3. Keep E2E workflows few, critical, and evidence-rich.
4. Prefer API-created state over slow UI setup.
5. Use explicit, registered Pytest markers.
6. A retry can gather evidence, but cannot erase a flaky result.
7. `xfail` entries require a linked defect, reason, and expiry policy.
