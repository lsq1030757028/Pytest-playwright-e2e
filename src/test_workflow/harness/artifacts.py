from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any, Protocol, runtime_checkable

from pydantic import Field

from .contracts import (
    ArtifactRef,
    ArtifactValidity,
    CapabilityExecutionContext,
    CapabilityRef,
    DomainEvent,
    FrozenModel,
)


class ArtifactStoreError(RuntimeError):
    pass


class ArtifactNotFoundError(ArtifactStoreError):
    pass


class ArtifactImmutableError(ArtifactStoreError):
    pass


class ArtifactIntegrityError(ArtifactStoreError):
    pass


class ArtifactEnvelope(FrozenModel):
    ref: ArtifactRef
    content: dict[str, Any]
    stored_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def canonical_json_bytes(content: dict[str, Any]) -> bytes:
    return json.dumps(
        content,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def content_hash(content: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(content)).hexdigest()


@runtime_checkable
class ArtifactStore(Protocol):
    def put(
        self,
        *,
        artifact_id: str,
        artifact_type: str,
        schema_version: int,
        content: dict[str, Any],
        created_by: CapabilityRef,
        source_revisions: dict[str, str] | None = None,
        validity: ArtifactValidity = ArtifactValidity.VALID,
    ) -> ArtifactRef: ...

    def get(self, ref_or_id: ArtifactRef | str) -> ArtifactEnvelope: ...

    def exists(self, artifact_id: str) -> bool: ...

    def list_refs(self) -> tuple[ArtifactRef, ...]: ...


class InMemoryArtifactStore:
    def __init__(self) -> None:
        self._items: dict[str, ArtifactEnvelope] = {}
        self._lock = RLock()

    def put(
        self,
        *,
        artifact_id: str,
        artifact_type: str,
        schema_version: int,
        content: dict[str, Any],
        created_by: CapabilityRef,
        source_revisions: dict[str, str] | None = None,
        validity: ArtifactValidity = ArtifactValidity.VALID,
    ) -> ArtifactRef:
        ref = _build_ref(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            schema_version=schema_version,
            content=content,
            created_by=created_by,
            source_revisions=source_revisions,
            validity=validity,
        )
        envelope = ArtifactEnvelope(ref=ref, content=content)
        with self._lock:
            existing = self._items.get(artifact_id)
            if existing:
                _validate_idempotent_put(existing, envelope)
                return existing.ref
            self._items[artifact_id] = envelope
        return ref

    def get(self, ref_or_id: ArtifactRef | str) -> ArtifactEnvelope:
        artifact_id = ref_or_id.artifact_id if isinstance(ref_or_id, ArtifactRef) else ref_or_id
        with self._lock:
            try:
                envelope = self._items[artifact_id]
            except KeyError as exc:
                raise ArtifactNotFoundError(artifact_id) from exc
        _validate_envelope(envelope)
        if isinstance(ref_or_id, ArtifactRef) and envelope.ref != ref_or_id:
            raise ArtifactIntegrityError(f"artifact reference mismatch for {artifact_id}")
        return envelope

    def exists(self, artifact_id: str) -> bool:
        with self._lock:
            return artifact_id in self._items

    def list_refs(self) -> tuple[ArtifactRef, ...]:
        with self._lock:
            return tuple(self._items[key].ref for key in sorted(self._items))


class FileArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.objects_dir = self.root / "objects"
        self.objects_dir.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def put(
        self,
        *,
        artifact_id: str,
        artifact_type: str,
        schema_version: int,
        content: dict[str, Any],
        created_by: CapabilityRef,
        source_revisions: dict[str, str] | None = None,
        validity: ArtifactValidity = ArtifactValidity.VALID,
    ) -> ArtifactRef:
        ref = _build_ref(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            schema_version=schema_version,
            content=content,
            created_by=created_by,
            source_revisions=source_revisions,
            validity=validity,
        )
        envelope = ArtifactEnvelope(ref=ref, content=content)
        destination = self._path_for(artifact_id)
        with self._lock:
            if destination.exists():
                existing = self._read_path(destination)
                _validate_idempotent_put(existing, envelope)
                return existing.ref
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix(f".{os.getpid()}.tmp")
            temporary.write_text(envelope.model_dump_json(indent=2), encoding="utf-8")
            temporary.replace(destination)
        return ref

    def get(self, ref_or_id: ArtifactRef | str) -> ArtifactEnvelope:
        artifact_id = ref_or_id.artifact_id if isinstance(ref_or_id, ArtifactRef) else ref_or_id
        path = self._path_for(artifact_id)
        with self._lock:
            if not path.exists():
                raise ArtifactNotFoundError(artifact_id)
            envelope = self._read_path(path)
        if envelope.ref.artifact_id != artifact_id:
            raise ArtifactIntegrityError(f"artifact id mismatch for {artifact_id}")
        if isinstance(ref_or_id, ArtifactRef) and envelope.ref != ref_or_id:
            raise ArtifactIntegrityError(f"artifact reference mismatch for {artifact_id}")
        return envelope

    def exists(self, artifact_id: str) -> bool:
        return self._path_for(artifact_id).exists()

    def list_refs(self) -> tuple[ArtifactRef, ...]:
        refs: list[ArtifactRef] = []
        with self._lock:
            for path in sorted(self.objects_dir.glob("*/*.json")):
                refs.append(self._read_path(path).ref)
        return tuple(sorted(refs, key=lambda item: item.artifact_id))

    def object_path(self, artifact_id: str) -> Path:
        return self._path_for(artifact_id)

    def _path_for(self, artifact_id: str) -> Path:
        digest = hashlib.sha256(artifact_id.encode("utf-8")).hexdigest()
        return self.objects_dir / digest[:2] / f"{digest}.json"

    @staticmethod
    def _read_path(path: Path) -> ArtifactEnvelope:
        try:
            envelope = ArtifactEnvelope.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ArtifactIntegrityError(f"invalid artifact envelope: {path}") from exc
        _validate_envelope(envelope)
        expected_name = hashlib.sha256(envelope.ref.artifact_id.encode("utf-8")).hexdigest()
        if path.stem != expected_name:
            raise ArtifactIntegrityError(f"artifact index mismatch: {path}")
        return envelope


class StoreExecutionContext(CapabilityExecutionContext):
    def __init__(self, store: ArtifactStore) -> None:
        self.store = store
        self.events: list[DomainEvent] = []

    def read_artifact(self, ref: ArtifactRef) -> dict[str, Any]:
        return self.store.get(ref).content

    def write_artifact(
        self,
        *,
        artifact_id: str,
        artifact_type: str,
        schema_version: int,
        content: dict[str, Any],
        created_by: CapabilityRef,
        source_revisions: dict[str, str] | None = None,
    ) -> ArtifactRef:
        return self.store.put(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            schema_version=schema_version,
            content=content,
            created_by=created_by,
            source_revisions=source_revisions,
        )

    def emit(self, event: DomainEvent) -> None:
        self.events.append(event)


def _build_ref(
    *,
    artifact_id: str,
    artifact_type: str,
    schema_version: int,
    content: dict[str, Any],
    created_by: CapabilityRef,
    source_revisions: dict[str, str] | None,
    validity: ArtifactValidity,
) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        schema_version=schema_version,
        content_hash=content_hash(content),
        source_revisions=source_revisions or {},
        created_by=created_by,
        validity=validity,
    )


def _validate_envelope(envelope: ArtifactEnvelope) -> None:
    actual = content_hash(envelope.content)
    if actual != envelope.ref.content_hash:
        raise ArtifactIntegrityError(
            f"artifact hash mismatch for {envelope.ref.artifact_id}: "
            f"expected {envelope.ref.content_hash}, got {actual}"
        )


def _validate_idempotent_put(existing: ArtifactEnvelope, candidate: ArtifactEnvelope) -> None:
    _validate_envelope(existing)
    if existing.ref != candidate.ref or existing.content != candidate.content:
        raise ArtifactImmutableError(
            f"artifact {candidate.ref.artifact_id!r} already exists with different content"
        )
