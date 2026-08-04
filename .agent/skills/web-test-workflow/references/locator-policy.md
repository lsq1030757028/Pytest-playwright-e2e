# Locator policy

Priority order:

1. `get_by_role`
2. `get_by_label`
3. `get_by_text`
4. `get_by_placeholder`
5. stable `data-testid`
6. CSS only for stable semantic hooks

Avoid generated classes, DOM-depth selectors, positional XPath, and fixed waits.
