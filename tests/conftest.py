from __future__ import annotations

import re
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from examples.demo_app.main import app


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("workflow-playwright")
    group.addoption("--browser", action="store", default="chromium")
    group.addoption(
        "--tracing",
        action="store",
        default="off",
        choices=("off", "on", "retain-on-failure"),
    )
    group.addoption(
        "--screenshot",
        action="store",
        default="off",
        choices=("off", "on", "only-on-failure"),
    )
    group.addoption(
        "--video",
        action="store",
        default="off",
        choices=("off", "on", "retain-on-failure"),
    )
    group.addoption("--output", action="store", default="test-results")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[Any]) -> Iterator[None]:
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)


def _safe_test_name(nodeid: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", nodeid).strip("_")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="session")
def demo_server_url() -> Iterator[str]:
    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"{url}/health", timeout=0.5).is_success:
                break
        except httpx.HTTPError:
            time.sleep(0.05)
    else:
        server.should_exit = True
        thread.join(timeout=5)
        raise RuntimeError("demo server did not become healthy")

    yield url

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def playwright_engine() -> Iterator[Playwright]:
    with sync_playwright() as engine:
        yield engine


@pytest.fixture(scope="session")
def browser(
    playwright_engine: Playwright,
    pytestconfig: pytest.Config,
) -> Iterator[Browser]:
    browser_name = pytestconfig.getoption("--browser")
    browser_type = getattr(playwright_engine, browser_name, None)
    if browser_type is None:
        raise pytest.UsageError(f"unsupported browser: {browser_name}")
    launch_args: dict[str, Any] = {"headless": True}
    executable_candidates = [
        Path(browser_type.executable_path),
        Path("/usr/bin/chromium"),
        Path("/usr/bin/chromium-browser"),
        Path("/usr/bin/google-chrome"),
    ]
    executable_path = next((path for path in executable_candidates if path.exists()), None)
    if executable_path is not None:
        launch_args["executable_path"] = str(executable_path)
    instance = browser_type.launch(**launch_args)
    yield instance
    instance.close()


@pytest.fixture
def context(
    browser: Browser,
    pytestconfig: pytest.Config,
    request: pytest.FixtureRequest,
) -> Iterator[BrowserContext]:
    output_root = Path(pytestconfig.getoption("--output"))
    test_dir = output_root / _safe_test_name(request.node.nodeid)
    test_dir.mkdir(parents=True, exist_ok=True)

    video_mode = pytestconfig.getoption("--video")
    context_args: dict[str, Any] = {}
    if video_mode != "off":
        context_args["record_video_dir"] = str(test_dir / "video")
        context_args["record_video_size"] = {"width": 1280, "height": 720}

    browser_context = browser.new_context(**context_args)
    tracing_mode = pytestconfig.getoption("--tracing")
    if tracing_mode != "off":
        browser_context.tracing.start(screenshots=True, snapshots=True, sources=True)

    console_messages: list[str] = []
    failed_requests: list[str] = []
    browser_context.on(
        "page",
        lambda created_page: created_page.on(
            "console", lambda message: console_messages.append(f"{message.type}: {message.text}")
        ),
    )
    browser_context.on(
        "requestfailed",
        lambda req: failed_requests.append(f"{req.method} {req.url}: {req.failure}"),
    )

    yield browser_context

    failed = bool(getattr(request.node, "rep_call", None) and request.node.rep_call.failed)

    if console_messages:
        (test_dir / "browser-console.log").write_text(
            "\n".join(console_messages), encoding="utf-8"
        )
    if failed_requests:
        (test_dir / "failed-requests.log").write_text(
            "\n".join(failed_requests), encoding="utf-8"
        )

    if tracing_mode == "on" or (tracing_mode == "retain-on-failure" and failed):
        browser_context.tracing.stop(path=str(test_dir / "trace.zip"))
    elif tracing_mode != "off":
        browser_context.tracing.stop()

    browser_context.close()

    if video_mode == "retain-on-failure" and not failed:
        video_dir = test_dir / "video"
        if video_dir.exists():
            for file in video_dir.iterdir():
                file.unlink(missing_ok=True)
            video_dir.rmdir()



@pytest.fixture
def page(
    context: BrowserContext,
    pytestconfig: pytest.Config,
    request: pytest.FixtureRequest,
) -> Iterator[Page]:
    browser_page = context.new_page()
    console_messages: list[str] = []
    browser_page.on(
        "console", lambda message: console_messages.append(f"{message.type}: {message.text}")
    )

    yield browser_page

    failed = bool(getattr(request.node, "rep_call", None) and request.node.rep_call.failed)
    screenshot_mode = pytestconfig.getoption("--screenshot")
    should_capture = screenshot_mode == "on" or (
        screenshot_mode == "only-on-failure" and failed
    )
    if should_capture and not browser_page.is_closed():
        output_root = Path(pytestconfig.getoption("--output"))
        test_dir = output_root / _safe_test_name(request.node.nodeid)
        test_dir.mkdir(parents=True, exist_ok=True)
        browser_page.screenshot(path=str(test_dir / "screenshot.png"), full_page=True)

    if console_messages:
        output_root = Path(pytestconfig.getoption("--output"))
        test_dir = output_root / _safe_test_name(request.node.nodeid)
        test_dir.mkdir(parents=True, exist_ok=True)
        (test_dir / "page-console.log").write_text("\n".join(console_messages), encoding="utf-8")
