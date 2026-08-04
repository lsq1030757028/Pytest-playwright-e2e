import os

import pytest
from playwright.sync_api import Page

from tests.e2e.flows.free_time_flow import FreeTimeFlow


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_LIVE_E2E") != "1",
    reason="Set RUN_LIVE_E2E=1 in an environment that allows browser loopback access.",
)
def test_live_ui_calls_real_calculation_api(page: Page, demo_server_url: str) -> None:
    base_url = os.getenv("TEST_WORKFLOW_BASE_URL", demo_server_url)
    FreeTimeFlow(page).verify_result(
        base_url=base_url,
        free_minutes=2,
        close_seconds=120,
        expected_text="免费时长生效",
    )
