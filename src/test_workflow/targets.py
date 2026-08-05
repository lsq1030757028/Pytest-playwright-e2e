from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path

import httpx
from pydantic import BaseModel, Field, model_validator

from .serialization import load_model


class TargetManifest(BaseModel):
    schema_version: str = "1.0"
    id: str
    repository: str
    revision: str = Field(min_length=7)
    subdirectory: str = "."
    install_command: list[str] = Field(default_factory=list)
    start_command: list[str]
    health_path: str = "/"
    required_files: list[str] = Field(default_factory=list)
    environment: dict[str, str] = Field(default_factory=dict)
    attribution: str | None = None

    @model_validator(mode="after")
    def validate_commands_and_paths(self) -> TargetManifest:
        if not self.start_command:
            raise ValueError("start_command cannot be empty")
        if not self.health_path.startswith("/"):
            raise ValueError("health_path must start with '/'")
        if Path(self.subdirectory).is_absolute() or ".." in Path(self.subdirectory).parts:
            raise ValueError("subdirectory must remain inside the checkout")
        for required_file in self.required_files:
            path = Path(required_file)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("required_files must remain inside the checkout")
        return self


@dataclass(frozen=True)
class MaterializedTarget:
    manifest: TargetManifest
    checkout_dir: Path
    app_dir: Path
    revision: str


@dataclass(frozen=True)
class RunningTarget:
    target: MaterializedTarget
    base_url: str
    process: subprocess.Popen[str]
    stdout_path: Path
    stderr_path: Path


class TargetProcess(AbstractContextManager[RunningTarget]):
    def __init__(
        self,
        target: MaterializedTarget,
        *,
        port: int | None = None,
        log_dir: Path | None = None,
        timeout_seconds: float = 30,
    ) -> None:
        self.target = target
        self.port = port or find_free_port()
        self.log_dir = log_dir or (target.checkout_dir / ".test-workflow")
        self.timeout_seconds = timeout_seconds
        self._running: RunningTarget | None = None
        self._stdout_file = None
        self._stderr_file = None

    def __enter__(self) -> RunningTarget:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = self.log_dir / "target-stdout.log"
        stderr_path = self.log_dir / "target-stderr.log"
        self._stdout_file = stdout_path.open("w", encoding="utf-8")
        self._stderr_file = stderr_path.open("w", encoding="utf-8")

        command = [
            item.replace("${PORT}", str(self.port))
            for item in self.target.manifest.start_command
        ]
        environment = os.environ.copy()
        environment.update(self.target.manifest.environment)
        environment["PORT"] = str(self.port)
        process = subprocess.Popen(
            command,
            cwd=self.target.app_dir,
            env=environment,
            stdout=self._stdout_file,
            stderr=self._stderr_file,
            text=True,
        )
        base_url = f"http://127.0.0.1:{self.port}"
        running = RunningTarget(
            target=self.target,
            base_url=base_url,
            process=process,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
        self._running = running
        try:
            wait_for_health(
                f"{base_url}{self.target.manifest.health_path}",
                process=process,
                timeout_seconds=self.timeout_seconds,
            )
        except Exception:
            self.__exit__(None, None, None)
            raise
        return running

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self._running is not None:
            process = self._running.process
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        if self._stdout_file is not None:
            self._stdout_file.close()
        if self._stderr_file is not None:
            self._stderr_file.close()
        self._running = None
        return None


class TargetManager:
    def load_manifest(self, manifest_path: str | Path) -> TargetManifest:
        return load_model(manifest_path, TargetManifest)

    def materialize(
        self,
        manifest_path: str | Path,
        destination: str | Path,
        *,
        install: bool = True,
    ) -> MaterializedTarget:
        manifest = self.load_manifest(manifest_path)
        checkout = Path(destination).resolve()
        if checkout.exists():
            shutil.rmtree(checkout)
        checkout.parent.mkdir(parents=True, exist_ok=True)

        self._run(
            ["git", "clone", "--no-checkout", manifest.repository, str(checkout)],
            cwd=checkout.parent,
        )
        self._run(
            ["git", "-c", "advice.detachedHead=false", "checkout", manifest.revision],
            cwd=checkout,
        )
        revision = self._run(
            ["git", "rev-parse", "HEAD"],
            cwd=checkout,
            capture_output=True,
        ).stdout.strip()
        if revision != manifest.revision:
            raise ValueError(
                f"target revision mismatch: expected {manifest.revision}, got {revision}"
            )

        app_dir = (checkout / manifest.subdirectory).resolve()
        if not app_dir.is_relative_to(checkout) or not app_dir.is_dir():
            raise ValueError(f"target subdirectory does not exist: {manifest.subdirectory}")
        for required_file in manifest.required_files:
            path = app_dir / required_file
            if not path.is_file():
                raise ValueError(f"required target file missing: {required_file}")

        if install and manifest.install_command:
            self._run(manifest.install_command, cwd=app_dir)

        return MaterializedTarget(
            manifest=manifest,
            checkout_dir=checkout,
            app_dir=app_dir,
            revision=revision,
        )

    def validate_checkout(
        self,
        manifest_path: str | Path,
        checkout_dir: str | Path,
    ) -> MaterializedTarget:
        manifest = self.load_manifest(manifest_path)
        checkout = Path(checkout_dir).resolve()
        revision = self._run(
            ["git", "rev-parse", "HEAD"], cwd=checkout, capture_output=True
        ).stdout.strip()
        if revision != manifest.revision:
            raise ValueError(
                f"target revision mismatch: expected {manifest.revision}, got {revision}"
            )
        app_dir = (checkout / manifest.subdirectory).resolve()
        if not app_dir.is_relative_to(checkout):
            raise ValueError("target app directory escaped checkout")
        for required_file in manifest.required_files:
            if not (app_dir / required_file).is_file():
                raise ValueError(f"required target file missing: {required_file}")
        return MaterializedTarget(manifest, checkout, app_dir, revision)

    def process(
        self,
        target: MaterializedTarget,
        *,
        port: int | None = None,
        log_dir: Path | None = None,
        timeout_seconds: float = 30,
    ) -> TargetProcess:
        return TargetProcess(
            target,
            port=port,
            log_dir=log_dir,
            timeout_seconds=timeout_seconds,
        )

    @staticmethod
    def _run(
        command: list[str],
        *,
        cwd: Path,
        capture_output: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                command,
                cwd=cwd,
                check=True,
                text=True,
                capture_output=capture_output,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(f"required executable is missing: {command[0]}") from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            raise RuntimeError(
                f"command failed ({exc.returncode}): {' '.join(command)}\n{detail}"
            ) from exc


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_health(
    url: str,
    *,
    process: subprocess.Popen[str] | None = None,
    timeout_seconds: float = 30,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = "not attempted"
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise RuntimeError(
                "target process exited before becoming healthy: "
                f"{process.returncode}"
            )
        try:
            response = httpx.get(url, timeout=1)
            if response.is_success:
                return
            last_error = f"HTTP {response.status_code}"
        except httpx.HTTPError as exc:
            last_error = str(exc)
        time.sleep(0.1)
    raise TimeoutError(f"target did not become healthy at {url}: {last_error}")
