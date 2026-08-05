from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .serialization import load_model
from .specs import DataSeedSpec, EnvironmentSpec


@dataclass(frozen=True)
class RuntimeEnvironment:
    runtime_dir: Path
    storage_state_path: Path
    init_script_path: Path
    metadata_path: Path


def _storage_value(value: object) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def compile_storage_state(seed: DataSeedSpec, output_path: Path) -> Path:
    origins = []
    for item in seed.browser_storage:
        origins.append(
            {
                "origin": str(item.origin).rstrip("/"),
                "localStorage": [
                    {"name": name, "value": _storage_value(value)}
                    for name, value in sorted(item.local_storage.items())
                ],
            }
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps({"cookies": [], "origins": origins}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def compile_init_script(environment: EnvironmentSpec, output_path: Path) -> Path:
    fixed_time = (
        environment.clock.frozen_at.isoformat()
        if environment.clock.frozen_at is not None
        else None
    )
    script = f"""(() => {{
  let seed = {environment.random_seed} >>> 0;
  Math.random = () => {{
    seed = (1664525 * seed + 1013904223) >>> 0;
    return seed / 4294967296;
  }};
  const fixedIso = {json.dumps(fixed_time)};
  if (fixedIso) {{
    const NativeDate = Date;
    const fixedMillis = new NativeDate(fixedIso).valueOf();
    class ControlledDate extends NativeDate {{
      constructor(...args) {{
        super(...(args.length ? args : [fixedMillis]));
      }}
      static now() {{ return fixedMillis; }}
    }}
    Object.setPrototypeOf(ControlledDate, NativeDate);
    globalThis.Date = ControlledDate;
  }}
}})();
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(script, encoding="utf-8")
    return output_path


def build_runtime(bundle_root: str | Path) -> RuntimeEnvironment:
    root = Path(bundle_root).resolve()
    environment = load_model(
        root / "environment" / "environment-spec.yaml", EnvironmentSpec
    )
    seed = load_model(root / environment.data_seed_path, DataSeedSpec)

    runtime_dir = root / ".runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    storage_state = compile_storage_state(seed, runtime_dir / "storage-state.json")
    init_script = compile_init_script(environment, runtime_dir / "init-script.js")
    metadata = runtime_dir / "runtime.json"
    metadata.write_text(
        json.dumps(
            {
                "profile": environment.profile,
                "base_url": str(environment.base_url) if environment.base_url else None,
                "random_seed": environment.random_seed,
                "frozen_at": (
                    environment.clock.frozen_at.isoformat()
                    if environment.clock.frozen_at
                    else None
                ),
                "storage_state": str(storage_state),
                "init_script": str(init_script),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return RuntimeEnvironment(runtime_dir, storage_state, init_script, metadata)
