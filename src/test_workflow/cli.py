from __future__ import annotations

import json
from pathlib import Path

import typer

from .classifier import classify_failure
from .config import load_settings
from .models import FailureEvidence, QualityGate
from .preflight import run_preflight
from .reporting import parse_junit, render_markdown
from .runner import run_tests

app = typer.Typer(no_args_is_help=True, help="Pytest + Skill + Playwright workflow CLI")


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


if __name__ == "__main__":
    app()
