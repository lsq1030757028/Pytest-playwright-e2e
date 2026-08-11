from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml


class ManifestError(ValueError):
    """Raised when a BETA-A submission or referenced manifest is invalid."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_mapping(path: Path) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ManifestError(f"manifest unavailable: {path}") from exc
    except yaml.YAMLError as exc:
        raise ManifestError(f"manifest is not valid YAML: {path}") from exc
    if not isinstance(loaded, dict):
        raise ManifestError(f"manifest must be a mapping: {path}")
    return loaded


def _require(mapping: dict[str, Any], keys: set[str], *, label: str) -> None:
    missing = sorted(key for key in keys if key not in mapping)
    if missing:
        raise ManifestError(f"{label} missing required fields: {', '.join(missing)}")


def _resolve_ref(base: Path, raw: str, *, label: str) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise ManifestError(f"{label} must be a non-empty path")
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = base / candidate
    return candidate.resolve()


def _safe_node_id(node_id: str) -> None:
    if not isinstance(node_id, str) or "::" not in node_id:
        raise ManifestError(f"invalid exact pytest node id: {node_id!r}")
    path_part = node_id.split("::", 1)[0]
    pure = PurePosixPath(path_part.replace("\\", "/"))
    if pure.is_absolute() or ".." in pure.parts or path_part.startswith("-"):
        raise ManifestError(f"unsafe pytest node path: {node_id!r}")


def _path_allowed(node_id: str, permitted_paths: list[str]) -> bool:
    node_path = PurePosixPath(node_id.split("::", 1)[0].replace("\\", "/"))
    for raw in permitted_paths:
        permitted = PurePosixPath(str(raw).replace("\\", "/"))
        if permitted.is_absolute() or ".." in permitted.parts:
            raise ManifestError(f"unsafe permitted test path: {raw!r}")
        if node_path == permitted or permitted in node_path.parents:
            return True
    return False


@dataclass(frozen=True)
class ManifestRef:
    raw: str
    path: Path
    sha256: str
    data: dict[str, Any]

    def binding(self) -> dict[str, str]:
        return {"ref": self.raw, "sha256": self.sha256}


@dataclass(frozen=True)
class ProjectProfile:
    profile_id: str
    repository: str
    checkout_path: Path
    commit_sha: str
    execution_image: str
    network: str


@dataclass(frozen=True)
class GovernedPack:
    pack_id: str
    pack_version: str
    commit_sha: str
    selected_node_ids: tuple[str, ...]
    required_node_ids: tuple[str, ...]
    node_oracle_bindings: dict[str, str]


@dataclass(frozen=True)
class SubmissionBundle:
    manifest_path: Path
    submission: dict[str, Any]
    fingerprint: str
    project_profile_ref: ManifestRef
    pack_ref: ManifestRef
    objective_ref: ManifestRef
    environment_ref: ManifestRef
    budget_ref: ManifestRef
    evidence_ref: ManifestRef
    oracle_refs: tuple[ManifestRef, ...]
    project_profile: ProjectProfile
    pack: GovernedPack

    def durable_payload(self) -> dict[str, Any]:
        return {
            "submission": self.submission,
            "fingerprint": self.fingerprint,
            "bindings": {
                "project_profile": self.project_profile_ref.binding(),
                "governed_pack": self.pack_ref.binding(),
                "objective": self.objective_ref.binding(),
                "environment": self.environment_ref.binding(),
                "budget": self.budget_ref.binding(),
                "evidence": self.evidence_ref.binding(),
                "oracles": [item.binding() for item in self.oracle_refs],
            },
            "resolved": {
                "checkout_path": str(self.project_profile.checkout_path),
                "execution_image": self.project_profile.execution_image,
                "selected_node_ids": list(self.pack.selected_node_ids),
                "required_node_ids": list(self.pack.required_node_ids),
                "node_oracle_bindings": self.pack.node_oracle_bindings,
            },
        }


_SUBMISSION_REQUIRED = {
    "idempotency_key",
    "project_repository",
    "commit_sha",
    "project_profile_ref",
    "objective_manifest_ref",
    "governed_pack_manifest_ref",
    "permitted_test_paths",
    "permitted_capabilities",
    "oracle_refs",
    "environment_profile_ref",
    "budget_profile_ref",
    "evidence_profile_ref",
}

_PACK_REQUIRED = {
    "pack_id",
    "pack_version",
    "project_profile_ref",
    "commit_sha",
    "framework",
    "selected_node_ids",
    "required_node_ids",
    "node_oracle_bindings",
    "environment_profile_ref",
    "evidence_profile_ref",
}


def _manifest_ref(base: Path, raw: str, *, label: str) -> ManifestRef:
    path = _resolve_ref(base, raw, label=label)
    data = _load_mapping(path)
    return ManifestRef(raw=raw, path=path, sha256=sha256_file(path), data=data)


def _validate_budget(data: dict[str, Any]) -> None:
    maxima = {
        "wall_clock_job_minutes": 45,
        "execution_attempt_minutes": 15,
        "execution_attempts": 1,
        "workers_per_job": 1,
        "browser_contexts_per_attempt": 1,
        "artifact_mebibytes": 500,
        "automatic_retries": 0,
    }
    _require(data, set(maxima), label="budget profile")
    for key, maximum in maxima.items():
        value = data[key]
        if not isinstance(value, int) or value < 0 or value > maximum:
            raise ManifestError(f"budget {key} must be an integer <= {maximum}")
    if data["execution_attempts"] != 1 or data["workers_per_job"] != 1:
        raise ManifestError("BETA-A requires exactly one execution attempt and one worker")
    if data["browser_contexts_per_attempt"] != 1 or data["automatic_retries"] != 0:
        raise ManifestError("BETA-A requires one browser context and zero automatic retries")


def load_submission_bundle(manifest_path: Path) -> SubmissionBundle:
    manifest_path = manifest_path.resolve()
    submission = _load_mapping(manifest_path)
    _require(submission, _SUBMISSION_REQUIRED, label="submission")
    base = manifest_path.parent

    idempotency_key = submission["idempotency_key"]
    commit_sha = submission["commit_sha"]
    repository = submission["project_repository"]
    if not isinstance(idempotency_key, str) or not idempotency_key.strip():
        raise ManifestError("idempotency_key must be non-empty")
    if not isinstance(repository, str) or not repository.strip():
        raise ManifestError("project_repository must be non-empty")
    if not isinstance(commit_sha, str) or len(commit_sha) != 40:
        raise ManifestError("commit_sha must be a full 40-character Git SHA")

    list_fields = ("permitted_test_paths", "permitted_capabilities", "oracle_refs")
    for key in list_fields:
        if not isinstance(submission[key], list) or not submission[key]:
            raise ManifestError(f"{key} must be a non-empty list")

    permitted_capabilities = set(submission["permitted_capabilities"])
    if not permitted_capabilities <= {"pytest", "playwright", "chromium"}:
        raise ManifestError("unsupported permitted capability")
    if "pytest" not in permitted_capabilities:
        raise ManifestError("pytest capability is required")

    project_ref = _manifest_ref(base, submission["project_profile_ref"], label="project profile")
    pack_ref = _manifest_ref(base, submission["governed_pack_manifest_ref"], label="governed pack")
    objective_ref = _manifest_ref(base, submission["objective_manifest_ref"], label="objective")
    environment_ref = _manifest_ref(base, submission["environment_profile_ref"], label="environment")
    budget_ref = _manifest_ref(base, submission["budget_profile_ref"], label="budget")
    evidence_ref = _manifest_ref(base, submission["evidence_profile_ref"], label="evidence")
    oracle_refs = tuple(
        _manifest_ref(base, raw, label="oracle") for raw in submission["oracle_refs"]
    )

    _require(
        project_ref.data,
        {"profile_id", "repository", "checkout_path", "commit_sha"},
        label="project profile",
    )
    if project_ref.data["repository"] != repository:
        raise ManifestError("project profile repository does not match submission")
    if project_ref.data["commit_sha"] != commit_sha:
        raise ManifestError("project profile commit does not match submission")

    _require(environment_ref.data, {"backend", "image", "network"}, label="environment profile")
    if environment_ref.data["backend"] != "DOCKER":
        raise ManifestError("BETA-A reference profile requires DOCKER backend")
    if environment_ref.data["network"] != "DENY":
        raise ManifestError("BETA-A reference profile requires deny-by-default network")
    image = environment_ref.data["image"]
    if not isinstance(image, str) or not image.strip():
        raise ManifestError("environment image must be explicitly versioned")

    checkout_path = _resolve_ref(
        project_ref.path.parent,
        project_ref.data["checkout_path"],
        label="project checkout",
    )
    if not checkout_path.is_dir():
        raise ManifestError("project checkout directory does not exist")

    _validate_budget(budget_ref.data)
    _require(evidence_ref.data, {"profile_id", "capture"}, label="evidence profile")
    if not isinstance(evidence_ref.data["capture"], list):
        raise ManifestError("evidence capture must be a list")

    pack_data = pack_ref.data
    _require(pack_data, _PACK_REQUIRED, label="governed pack")
    if pack_data["framework"] not in {"pytest", "pytest-playwright"}:
        raise ManifestError("governed pack framework is unsupported")
    if pack_data["commit_sha"] != commit_sha:
        raise ManifestError("governed pack commit does not match submission")
    if pack_data["project_profile_ref"] != submission["project_profile_ref"]:
        raise ManifestError("governed pack project profile binding does not match submission")
    if pack_data["environment_profile_ref"] != submission["environment_profile_ref"]:
        raise ManifestError("governed pack environment binding does not match submission")
    if pack_data["evidence_profile_ref"] != submission["evidence_profile_ref"]:
        raise ManifestError("governed pack evidence binding does not match submission")

    selected = pack_data["selected_node_ids"]
    required = pack_data["required_node_ids"]
    bindings = pack_data["node_oracle_bindings"]
    if not isinstance(selected, list) or not selected or len(selected) != len(set(selected)):
        raise ManifestError("selected_node_ids must be a non-empty unique list")
    if not isinstance(required, list) or not required or not set(required) <= set(selected):
        raise ManifestError("required_node_ids must be a non-empty subset of selected_node_ids")
    if not isinstance(bindings, dict) or set(required) - set(bindings):
        raise ManifestError("every required node needs an Oracle binding")

    for node_id in selected:
        _safe_node_id(node_id)
        if not _path_allowed(node_id, submission["permitted_test_paths"]):
            raise ManifestError(f"node is outside permitted test paths: {node_id}")

    oracle_raw_refs = set(submission["oracle_refs"])
    for node_id in required:
        if bindings[node_id] not in oracle_raw_refs:
            raise ManifestError(f"required node Oracle is not authorized by submission: {node_id}")

    project_profile = ProjectProfile(
        profile_id=str(project_ref.data["profile_id"]),
        repository=repository,
        checkout_path=checkout_path,
        commit_sha=commit_sha,
        execution_image=image,
        network="DENY",
    )
    pack = GovernedPack(
        pack_id=str(pack_data["pack_id"]),
        pack_version=str(pack_data["pack_version"]),
        commit_sha=commit_sha,
        selected_node_ids=tuple(str(item) for item in selected),
        required_node_ids=tuple(str(item) for item in required),
        node_oracle_bindings={str(key): str(value) for key, value in bindings.items()},
    )

    bindings_for_fingerprint = {
        "submission": submission,
        "project_profile": project_ref.binding(),
        "governed_pack": pack_ref.binding(),
        "objective": objective_ref.binding(),
        "environment": environment_ref.binding(),
        "budget": budget_ref.binding(),
        "evidence": evidence_ref.binding(),
        "oracles": [item.binding() for item in oracle_refs],
    }
    fingerprint = sha256_bytes(canonical_json(bindings_for_fingerprint).encode("utf-8"))
    return SubmissionBundle(
        manifest_path=manifest_path,
        submission=submission,
        fingerprint=fingerprint,
        project_profile_ref=project_ref,
        pack_ref=pack_ref,
        objective_ref=objective_ref,
        environment_ref=environment_ref,
        budget_ref=budget_ref,
        evidence_ref=evidence_ref,
        oracle_refs=oracle_refs,
        project_profile=project_profile,
        pack=pack,
    )
