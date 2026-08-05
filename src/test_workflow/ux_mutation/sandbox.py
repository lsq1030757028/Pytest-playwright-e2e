from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..integrity import sha256_bytes, sha256_file
from ..targets import MaterializedTarget
from .models import PatchEvidence, UXMutation


def _digest(value: str) -> str:
    return value.removeprefix("sha256:")


def _git(checkout: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=checkout,
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout.strip()


def changed_files(checkout: Path) -> tuple[str, ...]:
    output = _git(checkout, "status", "--porcelain", "--untracked-files=all")
    if not output:
        return ()
    return tuple(sorted(line[3:] for line in output.splitlines() if len(line) >= 4))


@dataclass(frozen=True)
class AppliedPatch:
    mutation: UXMutation
    target_path: Path
    original_bytes: bytes
    preimage_sha256: str
    postimage_sha256: str
    changed_files: tuple[str, ...]
    observed_replacement_count: int


class TargetMutationSandbox:
    def __init__(self, target: MaterializedTarget, mutation: UXMutation) -> None:
        self.target = target
        self.mutation = mutation
        self.checkout = target.checkout_dir.resolve()
        self.app_dir = target.app_dir.resolve()
        self.target_path = (self.app_dir / mutation.target_path).resolve()
        self._applied: AppliedPatch | None = None

    def verify_clean_preimage(self) -> None:
        if not self.target_path.is_relative_to(self.app_dir):
            raise ValueError("mutation path escaped target application directory")
        if self.target_path.is_symlink():
            raise ValueError("mutation target cannot be a symbolic link")
        if not self.target_path.is_file():
            raise ValueError(f"mutation target file does not exist: {self.mutation.target_path}")
        if changed_files(self.checkout):
            raise ValueError("target checkout must be clean before mutation proof")
        observed = sha256_file(self.target_path)
        if observed != _digest(self.mutation.preimage_sha256):
            raise ValueError(
                f"mutation preimage hash mismatch for {self.mutation.mutation_id}: "
                f"expected={_digest(self.mutation.preimage_sha256)}, observed={observed}"
            )
        original = self.target_path.read_text(encoding="utf-8")
        if sha256_bytes(self.mutation.search_text.encode("utf-8")) != _digest(
            self.mutation.search_sha256
        ):
            raise ValueError("mutation search_text hash mismatch")
        if sha256_bytes(self.mutation.replacement_text.encode("utf-8")) != _digest(
            self.mutation.replacement_sha256
        ):
            raise ValueError("mutation replacement_text hash mismatch")
        observed_count = original.count(self.mutation.search_text)
        if observed_count != self.mutation.expected_replacement_count:
            raise ValueError(
                f"mutation {self.mutation.mutation_id} expected exactly one match, "
                f"observed={observed_count}"
            )

    def apply(self) -> AppliedPatch:
        if self._applied is not None:
            raise RuntimeError("mutation is already applied")
        self.verify_clean_preimage()
        original_bytes = self.target_path.read_bytes()
        original_text = original_bytes.decode("utf-8")
        observed_count = original_text.count(self.mutation.search_text)
        mutated_text = original_text.replace(
            self.mutation.search_text,
            self.mutation.replacement_text,
            1,
        )
        self.target_path.write_bytes(mutated_text.encode("utf-8"))
        postimage = sha256_file(self.target_path)
        if postimage != _digest(self.mutation.postimage_sha256):
            self.target_path.write_bytes(original_bytes)
            raise ValueError(
                f"mutation postimage hash mismatch for {self.mutation.mutation_id}: "
                f"expected={_digest(self.mutation.postimage_sha256)}, observed={postimage}"
            )
        observed_changes = changed_files(self.checkout)
        if observed_changes != (self.mutation.target_path,):
            self.target_path.write_bytes(original_bytes)
            raise ValueError(
                f"mutation changed undeclared files: {observed_changes}"
            )
        applied = AppliedPatch(
            mutation=self.mutation,
            target_path=self.target_path,
            original_bytes=original_bytes,
            preimage_sha256=sha256_bytes(original_bytes),
            postimage_sha256=postimage,
            changed_files=observed_changes,
            observed_replacement_count=observed_count,
        )
        self._applied = applied
        return applied

    def restore(self) -> PatchEvidence:
        if self._applied is None:
            raise RuntimeError("mutation has not been applied")
        applied = self._applied
        self.target_path.write_bytes(applied.original_bytes)
        restored_sha = sha256_file(self.target_path)
        restore_clean = not changed_files(self.checkout)
        if restored_sha != _digest(self.mutation.preimage_sha256):
            raise RuntimeError(
                f"mutation {self.mutation.mutation_id} did not restore exact source bytes"
            )
        if not restore_clean:
            raise RuntimeError(
                f"mutation {self.mutation.mutation_id} left a dirty target checkout"
            )
        self._applied = None
        return PatchEvidence(
            target_path=self.mutation.target_path,
            preimage_sha256=applied.preimage_sha256,
            search_sha256=sha256_bytes(self.mutation.search_text.encode("utf-8")),
            replacement_sha256=sha256_bytes(
                self.mutation.replacement_text.encode("utf-8")
            ),
            observed_replacement_count=applied.observed_replacement_count,
            postimage_sha256=applied.postimage_sha256,
            changed_files=applied.changed_files,
            restored_sha256=restored_sha,
            restore_clean=True,
        )

    def recover_if_needed(self) -> PatchEvidence | None:
        if self._applied is None:
            return None
        return self.restore()
