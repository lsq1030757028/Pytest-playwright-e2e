from __future__ import annotations

import os
import threading
import time

import pytest
import yaml

from test_workflow.beta_runtime.models import load_submission_bundle
from test_workflow.beta_runtime.runtime import RuntimeService
from test_workflow.beta_runtime.store import RuntimeStore
from tests.beta_a_helpers import make_governed_fixture, write_yaml

pytestmark = pytest.mark.skipif(
    not os.environ.get("BETA_A_DOCKER_IMAGE"),
    reason="BETA_A_DOCKER_IMAGE is required for the dedicated real-Docker gate",
)


def _expand_pack(manifests, submission_path, nodes):
    pack_path = manifests / "pack.yaml"
    pack = yaml.safe_load(pack_path.read_text(encoding="utf-8"))
    pack["framework"] = "pytest-playwright"
    pack["selected_node_ids"] = list(nodes)
    pack["required_node_ids"] = list(nodes)
    pack["node_oracle_bindings"] = {node: "oracle.yaml" for node in nodes}
    write_yaml(pack_path, pack)

    submission = yaml.safe_load(submission_path.read_text(encoding="utf-8"))
    submission["permitted_capabilities"] = ["pytest", "playwright", "chromium"]
    write_yaml(submission_path, submission)
    return load_submission_bundle(submission_path)


def test_real_docker_pytest_playwright_is_durable_replayable_and_isolated(tmp_path, monkeypatch):
    image = os.environ["BETA_A_DOCKER_IMAGE"]
    host_secret = "BETA_A_SHOULD_NOT_REACH_CONTAINER"
    monkeypatch.setenv("BETA_A_HOST_SECRET", host_secret)
    source = r'''
import os
import socket
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


def test_governed_unit():
    assert 2 + 2 == 4


def test_governed_browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content("<main><h1>BETA-A</h1></main>")
        assert page.locator("h1").inner_text() == "BETA-A"
        browser.close()


def test_governed_boundaries():
    assert os.environ.get("BETA_A_HOST_SECRET") is None
    with pytest.raises(OSError):
        Path("product-write-probe.txt").write_text("forbidden", encoding="utf-8")
    sock = socket.socket()
    sock.settimeout(0.25)
    with pytest.raises(OSError):
        sock.connect(("1.1.1.1", 80))
    sock.close()
'''
    _, project, manifests, submission_path = make_governed_fixture(
        tmp_path,
        image=image,
        test_source=source,
    )
    nodes = (
        "tests/test_governed.py::test_governed_unit",
        "tests/test_governed.py::test_governed_browser",
        "tests/test_governed.py::test_governed_boundaries",
    )
    bundle = _expand_pack(manifests, submission_path, nodes)
    state = tmp_path / "state"
    service = RuntimeService(state)
    job, created = service.submit(bundle)
    assert created is True
    assert job.state == "ACCEPTED"

    assert service.serve_once(worker_id="docker-worker") == job.job_id
    terminal = RuntimeStore(state).get_job(job.job_id)
    assert terminal.state == "SUCCEEDED"
    assert terminal.result["verdict"] == "VERIFIED_SUCCESS"
    assert terminal.result["automatic_reexecution"] is False
    assert terminal.result["project_source_digest_before"] == terminal.result["project_source_digest_after"]
    assert not (project / "product-write-probe.txt").exists()
    assert {"junit", "runtime_report", "collection", "entry_meta"} <= set(
        terminal.result["artifacts"]
    )

    restarted = RuntimeService(state)
    after_restart = restarted.store.get_job(job.job_id)
    assert after_restart.state == "SUCCEEDED"
    assert after_restart.result == terminal.result
    assert restarted.serve_once(worker_id="restart-worker") is None

    for ref in terminal.result["artifacts"].values():
        assert restarted.artifacts.verify(ref)
    assert restarted.artifacts.verify(terminal.result["evidence_manifest"])


def test_real_docker_cancellation_only_finishes_after_container_cleanup(tmp_path):
    image = os.environ["BETA_A_DOCKER_IMAGE"]
    source = r'''
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright


def test_governed_unit():
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content("<p>cancel-me</p>")
        try:
            time.sleep(120)
        finally:
            browser.close()
            child.terminate()
'''
    bundle, _, _, _ = make_governed_fixture(
        tmp_path,
        image=image,
        test_source=source,
    )
    state = tmp_path / "state"
    service = RuntimeService(state)
    job, _ = service.submit(bundle)

    thread = threading.Thread(
        target=lambda: service.serve_once(worker_id="cancel-worker"),
        daemon=True,
    )
    thread.start()

    deadline = time.monotonic() + 30
    attempt = None
    while time.monotonic() < deadline:
        attempt = service.store.attempt_for_job(job.job_id)
        if attempt is not None and bool(attempt["command_started"]):
            break
        time.sleep(0.05)
    assert attempt is not None and bool(attempt["command_started"])

    service.store.request_cancel(job.job_id)
    thread.join(timeout=30)
    assert not thread.is_alive()

    terminal = RuntimeStore(state).get_job(job.job_id)
    assert terminal.state == "CANCELLED"
    assert terminal.result["verdict"] == "CANCELLED"
    assert terminal.result["cleanup_verified"] is True
    assert terminal.result["artifacts"]
    assert RuntimeService(state).serve_once(worker_id="post-cancel") is None
