from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import canonical_json

_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization:\s*bearer\s+)[^\s]+"),
    re.compile(r"(?i)((?:token|password|secret|api[_-]?key)\s*[=:]\s*)[^\s,;]+"),
)


@dataclass(frozen=True)
class ArtifactRef:
    sha256: str
    size: int
    relative_path: str
    media_type: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "sha256": self.sha256,
            "size": self.size,
            "relative_path": self.relative_path,
            "media_type": self.media_type,
        }


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.objects = self.root / "objects"
        self.tmp = self.root / "tmp"
        self.objects.mkdir(parents=True, exist_ok=True)
        self.tmp.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def redact_text(text: str) -> str:
        value = text
        for pattern in _SECRET_PATTERNS:
            value = pattern.sub(r"\1[REDACTED]", value)
        return value

    @staticmethod
    def bounded_text(text: str, *, limit_bytes: int = 1024 * 1024) -> bytes:
        redacted = ArtifactStore.redact_text(text).encode("utf-8", errors="replace")
        if len(redacted) <= limit_bytes:
            return redacted
        marker = b"\n[TRUNCATED_BY_BETA_A_RUNTIME]\n"
        return redacted[: max(0, limit_bytes - len(marker))] + marker

    def put_text(
        self,
        text: str,
        *,
        media_type: str = "text/plain; charset=utf-8",
        limit_bytes: int = 1024 * 1024,
    ) -> ArtifactRef:
        return self.put_bytes(self.bounded_text(text, limit_bytes=limit_bytes), media_type=media_type)

    def put_json(self, value: Any) -> ArtifactRef:
        data = (canonical_json(value) + "\n").encode("utf-8")
        return self.put_bytes(data, media_type="application/json")

    def put_file(self, source: Path, *, media_type: str = "application/octet-stream") -> ArtifactRef:
        return self.put_bytes(source.read_bytes(), media_type=media_type)

    def put_bytes(self, data: bytes, *, media_type: str) -> ArtifactRef:
        digest = hashlib.sha256(data).hexdigest()
        destination = self.objects / digest[:2] / digest
        relative = destination.relative_to(self.root).as_posix()
        if destination.exists():
            if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                raise RuntimeError("existing content-addressed artifact failed hash verification")
            return ArtifactRef(digest, len(data), relative, media_type)

        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix="artifact-", dir=self.tmp)
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            if hashlib.sha256(temp_path.read_bytes()).hexdigest() != digest:
                raise RuntimeError("temporary artifact hash verification failed")
            os.replace(temp_path, destination)
            self._fsync_dir(destination.parent)
        finally:
            temp_path.unlink(missing_ok=True)
        return ArtifactRef(digest, len(data), relative, media_type)

    def resolve(self, ref: ArtifactRef | dict[str, Any]) -> Path:
        relative = ref.relative_path if isinstance(ref, ArtifactRef) else str(ref["relative_path"])
        candidate = (self.root / relative).resolve()
        if self.root not in candidate.parents:
            raise RuntimeError("artifact path escapes content-addressed store")
        return candidate

    def verify(self, ref: ArtifactRef | dict[str, Any]) -> bool:
        digest = ref.sha256 if isinstance(ref, ArtifactRef) else str(ref["sha256"])
        path = self.resolve(ref)
        if not path.is_file():
            return False
        calculated = hashlib.sha256(path.read_bytes()).hexdigest()
        return calculated == digest

    @staticmethod
    def _fsync_dir(path: Path) -> None:
        flags = getattr(os, "O_DIRECTORY", 0) | os.O_RDONLY
        fd = os.open(path, flags)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
