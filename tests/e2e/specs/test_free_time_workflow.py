import pytest
from playwright.sync_api import Page

from examples.demo_app.main import INDEX_HTML
from tests.e2e.flows.free_time_flow import FreeTimeFlow


@pytest.mark.e2e
@pytest.mark.smoke
@pytest.mark.critical
def test_free_time_applies_within_boundary(page: Page) -> None:
    FreeTimeFlow(page).verify_inline_result(
        html=INDEX_HTML,
        free_minutes=2,
        close_seconds=120,
        expected_text="免费时长生效",
    )


@pytest.mark.e2e
@pytest.mark.regression
def test_free_time_does_not_apply_after_boundary(page: Page) -> None:
    FreeTimeFlow(page).verify_inline_result(
        html=INDEX_HTML,
        free_minutes=2,
        close_seconds=121,
        expected_text="免费时长不生效",
    )
