from playwright.sync_api import Page, expect

from tests.e2e.pages.calculator_page import CalculatorPage


class FreeTimeFlow:
    def __init__(self, page: Page) -> None:
        self.calculator = CalculatorPage(page)

    def verify_result(
        self,
        base_url: str,
        free_minutes: int,
        close_seconds: int,
        expected_text: str,
    ) -> None:
        self.calculator.open(base_url)
        self._calculate_and_assert(free_minutes, close_seconds, expected_text)

    def verify_inline_result(
        self,
        html: str,
        free_minutes: int,
        close_seconds: int,
        expected_text: str,
    ) -> None:
        self.calculator.open_inline(html)
        self._calculate_and_assert(free_minutes, close_seconds, expected_text)

    def _calculate_and_assert(
        self,
        free_minutes: int,
        close_seconds: int,
        expected_text: str,
    ) -> None:
        self.calculator.calculate(free_minutes, close_seconds)
        expect(self.calculator.result).to_have_text(expected_text)
