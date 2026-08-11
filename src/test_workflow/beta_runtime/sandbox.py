from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .models import canonical_json


class SandboxUnavailable(RuntimeError):
    pass


class SandboxPolicyError(RuntimeError):
    pass


@dataclass(frozen=True)
class DockerRunResult:
    exit_code: int
    stdout: str
    stderr: str
    cancelled: bool
    timed_out: bool
    cleanup_verified: bool
    container_name: str


def _minimal_host_env() -> dict[str, str]:
    value = {"PATH": os.environ.get("PATH", "")}
    if os.environ.get("DOCKER_HOST"):
        value["DOCKER_HOST"] = os.environ["DOCKER_HOST"]
    return value


def _safe_mount_source(path: Path) -> str:
    value = str(path.resolve())
    if any(character in value for character in (",", "\n", "\r")):
        raise SandboxPolicyError("Docker bind source contains unsupported characters")
    return value


def validate_project_tree(root: Path) -> None:
    root = root.resolve()
    for path in root.rglob("*"):
        if not path.is_symlink():
            continue
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise SandboxPolicyError(f"broken project symlink: {path}") from exc
        if resolved != root and root not in resolved.parents:
            raise SandboxPolicyError(f"project symlink escapes root: {path}")


def source_tree_digest(root: Path) -> str:
    root = root.resolve()
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root)
        if ".git" in relative.parts:
            continue
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        if path.is_symlink():
            digest.update(b"SYMLINK\0")
            digest.update(os.readlink(path).encode("utf-8"))
        elif path.is_file():
            digest.update(b"FILE\0")
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        elif path.is_dir():
            digest.update(b"DIR\0")
        digest.update(b"\0")
    return digest.hexdigest()


class DockerSandbox:
    def __init__(self) -> None:
        package_dir = Path(__file__).resolve().parent
        self.entry_path = package_dir / "container_entry.py"
        self.plugin_path = package_dir / "pytest_plugin.py"

    def ensure_available(self, image: str) -> None:
        if shutil.which("docker") is None:
            raise SandboxUnavailable(
                "Docker CLI is unavailable; host-subprocess fallback is forbidden"
            )
        info = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            env=_minimal_host_env(),
            timeout=20,
            check=False,
        )
        if info.returncode != 0:
            raise SandboxUnavailable(
                f"Docker daemon is unavailable: {info.stderr.strip()}"
            )
        inspect = subprocess.run(
            ["docker", "image", "inspect", image],
            capture_output=True,
            text=True,
            env=_minimal_host_env(),
            timeout=20,
            check=False,
        )
        if inspect.returncode != 0:
            raise SandboxUnavailable(
                "execution image is not locally available; "
                "runtime will not pull images implicitly"
            )

    def command_manifest(
        self,
        *,
        image: str,
        project_path: Path,
        selected_node_ids: tuple[str, ...],
        attempt_id: str,
    ) -> dict[str, object]:
        return {
            "backend": "DOCKER",
            "image": image,
            "attempt_id": attempt_id,
            "project_path": str(project_path.resolve()),
            "project_mount": "/project:ro",
            "network": "none",
            "rootfs_read_only": True,
            "capabilities": "drop_all",
            "no_new_privileges": True,
            "selected_node_ids": list(selected_node_ids),
            "shell_interpolation": False,
            "automatic_retry": False,
        }

    def run(
        self,
        *,
        image: str,
        project_path: Path,
        scratch_path: Path,
        selected_node_ids: tuple[str, ...],
        attempt_id: str,
        timeout_seconds: float,
        cancel_requested: Callable[[], bool],
        heartbeat: Callable[[float], None],
        heartbeat_interval_seconds: float = 2.0,
    ) -> DockerRunResult:
        self.ensure_available(image)
        validate_project_tree(project_path)
        scratch_path = scratch_path.resolve()
        scratch_path.mkdir(parents=True, exist_ok=True)
        scratch_path.chmod(0o700)
        command_input = scratch_path / "command-input.json"
        command_input.write_text(
            canonical_json({"selected_node_ids": list(selected_node_ids)}) + "\n",
            encoding="utf-8",
        )
        container_name = "beta-a-" + "".join(
            character if character.isalnum() or character in "_.-" else "-"
            for character in attempt_id
        )[:100]
        project_mount = _safe_mount_source(project_path)
        evidence_mount = _safe_mount_source(scratch_path)
        entry_mount = _safe_mount_source(self.entry_path)
        plugin_mount = _safe_mount_source(self.plugin_path)
        argv = [
            "docker",
            "run",
            "--rm",
            "--name",
            container_name,
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--pids-limit",
            "256",
            "--memory",
            "1g",
            "--cpus",
            "2",
            "--shm-size",
            "256m",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=268435456",
            "--mount",
            f"type=bind,src={project_mount},dst=/project,readonly",
            "--mount",
            f"type=bind,src={evidence_mount},dst=/evidence",
            "--mount",
            f"type=bind,src={entry_mount},dst=/runtime/container_entry.py,readonly",
            "--mount",
            f"type=bind,src={plugin_mount},dst=/runtime/beta_a_pytest_plugin.py,readonly",
            "-e",
            "PYTHONPATH=/runtime",
            "-e",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
            "-e",
            "PYTHONDONTWRITEBYTECODE=1",
            "-w",
            "/project",
            image,
            "python",
            "/runtime/container_entry.py",
        ]
        process = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
            env=_minimal_host_env(),
        )
        started = time.monotonic()
        last_heartbeat = started
        cancelled = False
        timed_out = False
        stdout = ""
        stderr = ""
        try:
            while True:
                elapsed = time.monotonic() - started
                if not cancelled and not timed_out and cancel_requested():
                    cancelled = True
                    self._terminate(
                        container_name,
                        heartbeat=heartbeat,
                        heartbeat_interval_seconds=heartbeat_interval_seconds,
                    )
                elif not cancelled and not timed_out and elapsed >= timeout_seconds:
                    timed_out = True
                    self._terminate(
                        container_name,
                        heartbeat=heartbeat,
                        heartbeat_interval_seconds=heartbeat_interval_seconds,
                    )

                now = time.monotonic()
                if now - last_heartbeat >= heartbeat_interval_seconds:
                    heartbeat(time.time())
                    last_heartbeat = now
                try:
                    stdout, stderr = process.communicate(timeout=0.25)
                    break
                except subprocess.TimeoutExpired:
                    continue

            self._force_remove(container_name)
            cleanup_verified = self._cleanup_verified(container_name)
            return DockerRunResult(
                exit_code=int(process.returncode),
                stdout=stdout,
                stderr=stderr,
                cancelled=cancelled,
                timed_out=timed_out,
                cleanup_verified=cleanup_verified,
                container_name=container_name,
            )
        finally:
            if process.poll() is None:
                self._force_remove(container_name)
                try:
                    process.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()
            self._force_remove(container_name)

    @classmethod
    def _terminate(
        cls,
        container_name: str,
        *,
        heartbeat: Callable[[float], None],
        heartbeat_interval_seconds: float,
    ) -> None:
        cls._signal(container_name, "TERM")
        deadline = time.monotonic() + 10.0
        last_heartbeat = time.monotonic()
        while time.monotonic() < deadline:
            if not cls._is_running(container_name):
                return
            now = time.monotonic()
            if now - last_heartbeat >= heartbeat_interval_seconds:
                heartbeat(time.time())
                last_heartbeat = now
            time.sleep(0.2)
        cls._signal(container_name, "KILL")

    @staticmethod
    def _signal(container_name: str, signal_name: str) -> None:
        subprocess.run(
            ["docker", "kill", "--signal", signal_name, container_name],
            capture_output=True,
            text=True,
            env=_minimal_host_env(),
            timeout=10,
            check=False,
        )

    @staticmethod
    def _is_running(container_name: str) -> bool:
        inspect = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Running}}", container_name],
            capture_output=True,
            text=True,
            env=_minimal_host_env(),
            timeout=10,
            check=False,
        )
        return inspect.returncode == 0 and inspect.stdout.strip().lower() == "true"

    @staticmethod
    def _force_remove(container_name: str) -> None:
        subprocess.run(
            ["docker", "rm", "-f", container_name],
            capture_output=True,
            text=True,
            env=_minimal_host_env(),
            timeout=10,
            check=False,
        )

    @staticmethod
    def _cleanup_verified(container_name: str) -> bool:
        inspect = subprocess.run(
            ["docker", "inspect", container_name],
            capture_output=True,
            text=True,
            env=_minimal_host_env(),
            timeout=10,
            check=False,
        )
        return inspect.returncode != 0
