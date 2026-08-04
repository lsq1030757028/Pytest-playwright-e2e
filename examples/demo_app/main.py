from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Free Time Calculator Demo")

INDEX_HTML = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>免费关台计算器</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 680px; margin: 60px auto; padding: 0 20px; }
    form { display: grid; gap: 16px; }
    label { display: grid; gap: 6px; font-weight: 600; }
    input, button { font: inherit; padding: 10px 12px; }
    button { cursor: pointer; }
    #result { margin-top: 24px; padding: 16px; border: 1px solid #aaa; border-radius: 8px; }
  </style>
</head>
<body>
  <main>
    <h1>免费关台计算器</h1>
    <p>当关台耗时不超过配置的免费时长时，免费时长生效。</p>
    <form id="calculator">
      <label>免费时长（分钟）
        <input aria-label="免费时长（分钟）" id="free-minutes" type="number" min="0" value="2">
      </label>
      <label>关台耗时（秒）
        <input aria-label="关台耗时（秒）" id="close-seconds" type="number" min="0" value="119">
      </label>
      <button type="submit">计算</button>
    </form>
    <section id="result" role="status" aria-live="polite">等待计算</section>
  </main>
  <script>
    document.querySelector('#calculator').addEventListener('submit', async (event) => {
      event.preventDefault();
      const payload = {
        free_minutes: Number(document.querySelector('#free-minutes').value),
        close_seconds: Number(document.querySelector('#close-seconds').value),
      };
      const response = await fetch('/api/calculate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      document.querySelector('#result').textContent = data.free_time_applied
        ? '免费时长生效'
        : '免费时长不生效';
    });
  </script>
</body>
</html>
"""


class CalculationRequest(BaseModel):
    free_minutes: int = Field(ge=0, le=60)
    close_seconds: int = Field(ge=0, le=7200)


class CalculationResponse(BaseModel):
    free_time_applied: bool
    free_seconds: int
    close_seconds: int


def calculate_free_time(free_minutes: int, close_seconds: int) -> CalculationResponse:
    free_seconds = free_minutes * 60
    applied = free_minutes > 0 and close_seconds <= free_seconds
    return CalculationResponse(
        free_time_applied=applied,
        free_seconds=free_seconds,
        close_seconds=close_seconds,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/calculate", response_model=CalculationResponse)
def calculate(request: CalculationRequest) -> CalculationResponse:
    return calculate_free_time(request.free_minutes, request.close_seconds)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML
