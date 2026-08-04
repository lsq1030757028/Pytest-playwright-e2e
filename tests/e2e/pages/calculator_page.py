from playwright.sync_api import Page, expect


class CalculatorPage:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.heading = page.get_by_role("heading", name="免费关台计算器")
        self.free_minutes = page.get_by_label("免费时长（分钟）")
        self.close_seconds = page.get_by_label("关台耗时（秒）")
        self.calculate_button = page.get_by_role("button", name="计算")
        self.result = page.get_by_role("status")

    def open(self, base_url: str) -> None:
        self.page.goto(base_url)
        expect(self.heading).to_be_visible()

    def open_inline(self, html: str) -> None:
        self.page.set_content(html)
        self.page.evaluate(
            """
            () => {
              window.fetch = async (_url, options) => {
                const payload = JSON.parse(options.body);
                const freeSeconds = payload.free_minutes * 60;
                return {
                  json: async () => ({
                    free_time_applied:
                      payload.free_minutes > 0 && payload.close_seconds <= freeSeconds,
                    free_seconds: freeSeconds,
                    close_seconds: payload.close_seconds,
                  }),
                };
              };
            }
            """
        )
        expect(self.heading).to_be_visible()

    def calculate(self, free_minutes: int, close_seconds: int) -> None:
        self.free_minutes.fill(str(free_minutes))
        self.close_seconds.fill(str(close_seconds))
        self.calculate_button.click()
