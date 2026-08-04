from __future__ import annotations

import json
import shlex
from pathlib import Path

import typer
import uvicorn

from .bundle import create_replay_manifest, replay_bundle, validate_replay_bundle
from .classifier import classify_failure
from .config import load_settings
from .control_plane import build_runtime
from .mocking import validate_mock_configuration
from .models import FailureEvidence, QualityGate
from .preflight import run_preflight
from .reporting import parse_junit, render_markdown
from .runner import run_tests
from .serialization import load_model
from .specs import EnvironmentSpec, MockPlan, TestSpec
from .virtual_service import create_virtual_service, load_behavior

app = typer.Typer(no_args_is_help=True, help="Pytest + Skill + Playwright workflow CLI")
spec_app = typer.Typer(no_args_is_help=True, help="Validate structured test specifications")
bundle_app = typer.Typer(no_args_is_help=True, help="Create and validate replay bundles")
env_app = typer.Typer(no_args_is_help=True, help="Compile deterministic test environments")
mock_app = typer.Typer(no_args_is_help=True, help="Validate and run contract-backed mocks")
app.add_typer(spec_app, name="spec")
app.add_typer(bundle_app, name="bundle")
app.add_typer(env_app, name="env")
app.add_typer(mock_app, name="mock")


@app.command()
def preflight(config: Path = typer.Option(..., exists=True, readable=True)) -> None:
    """Validate environment, health endpoint, artifact storage, and write policy."""
    result = run_preflight(load_settings(config))
    typer.echo(result.model_dump_json(indent=2))
    if result.status == QualityGate.BLOCKED:
        raise typer.Exit(code=2)


@app.command("run")
def run_command(
    config: Path = typer.Option(..., exists=True, readable=True),
    marker: str = typer.Option("smoke and not destructive"),
    browser: str = typer.Option("chromium"),
) -> None:
    """Execute a guarded Pytest selection with Playwright evidence enabled."""
    settings = load_settings(config)
    preflight_result = run_preflight(settings)
    if preflight_result.status == QualityGate.BLOCKED:
        typer.echo(preflight_result.model_dump_json(indent=2))
        raise typer.Exit(code=2)
    raise typer.Exit(code=run_tests(settings, marker, browser))


@app.command()
def classify(input_file: Path = typer.Argument(..., exists=True, readable=True)) -> None:
    """Classify a structured failure evidence JSON file."""
    evidence = FailureEvidence.model_validate_json(input_file.read_text(encoding="utf-8"))
    typer.echo(classify_failure(evidence).model_dump_json(indent=2))


@app.command()
def report(
    junit_file: Path = typer.Argument(..., exists=True, readable=True),
    output: Path = typer.Option(Path("test-results/report.md")),
) -> None:
    """Convert a JUnit XML result into a concise quality-gate report."""
    summary = parse_junit(junit_file)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_markdown(summary), encoding="utf-8")
    typer.echo(json.dumps({"output": str(output), "quality_gate": summary.gate}, indent=2))


@spec_app.command("validate")
def validate_spec(
    spec_file: Path = typer.Argument(..., exists=True, readable=True),
) -> None:
    """Validate a TestSpec and all Oracle basis references."""
    spec = load_model(spec_file, TestSpec)
    typer.echo(
        json.dumps(
            {
                "valid": True,
                "spec_id": spec.id,
                "cases": len(spec.cases),
                "oracles": sum(len(case.oracles) for case in spec.cases),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


@env_app.command("build")
def build_environment(
    bundle_root: Path = typer.Argument(..., exists=True, file_okay=False),
) -> None:
    """Compile clock, randomness, and browser storage into runtime artifacts."""
    runtime = build_runtime(bundle_root)
    typer.echo(
        json.dumps(
            {
                "runtime_dir": str(runtime.runtime_dir),
                "storage_state": str(runtime.storage_state_path),
                "init_script": str(runtime.init_script_path),
            },
            indent=2,
        )
    )


@mock_app.command("verify")
def verify_mock_plan(
    bundle_root: Path = typer.Argument(..., exists=True, file_okay=False),
) -> None:
    """Verify truth boundaries, contract hashes, and mock response schemas."""
    result = validate_mock_configuration(bundle_root)
    typer.echo(result.model_dump_json(indent=2))
    if not result.valid:
        raise typer.Exit(code=2)


@mock_app.command("serve")
def serve_mock(
    bundle_root: Path = typer.Argument(..., exists=True, file_okay=False),
    dependency: str = typer.Argument(...),
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(9000, min=1, max=65535),
) -> None:
    """Run one contract-verified virtual service declared in the MockPlan."""
    root = bundle_root.resolve()
    environment = load_model(
        root / "environment" / "environment-spec.yaml", EnvironmentSpec
    )
    plan = load_model(root / environment.mock_plan_path, MockPlan)
    selected = next(
        (item for item in plan.dependencies if item.dependency == dependency), None
    )
    if selected is None or not selected.behavior_path:
        raise typer.BadParameter(f"no behavior configured for dependency {dependency!r}")
    report = validate_mock_configuration(root)
    if not report.valid:
        typer.echo(report.model_dump_json(indent=2))
        raise typer.Exit(code=2)
    behavior = load_behavior(root / selected.behavior_path)
    uvicorn.run(create_virtual_service(behavior), host=host, port=port)


@bundle_app.command("create")
def create_bundle(
    bundle_root: Path = typer.Argument(..., exists=True, file_okay=False),
    command: str = typer.Option(..., help="Replay command, parsed with shell quoting rules"),
    browser: str = typer.Option("chromium"),
    run_id: str | None = typer.Option(None),
) -> None:
    """Create a hash-pinned ReplayManifest for an existing bundle directory."""
    manifest = create_replay_manifest(
        bundle_root,
        command=shlex.split(command),
        browser=browser,
        run_id=run_id,
    )
    typer.echo(manifest.model_dump_json(indent=2))


@bundle_app.command("validate")
def validate_bundle(
    bundle_root: Path = typer.Argument(..., exists=True, file_okay=False),
    without_manifest: bool = typer.Option(False),
) -> None:
    """Validate bundle schemas, truth boundaries, contracts, and artifact hashes."""
    report = validate_replay_bundle(bundle_root, verify_manifest=not without_manifest)
    typer.echo(report.model_dump_json(indent=2))
    if not report.valid:
        raise typer.Exit(code=2)


@app.command()
def replay(
    bundle_root: Path = typer.Argument(..., exists=True, file_okay=False),
) -> None:
    """Independently replay a hash-pinned bundle without model participation."""
    try:
        return_code = replay_bundle(bundle_root)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=2) from exc
    raise typer.Exit(code=return_code)


if __name__ == "__main__":
    app()
