from __future__ import annotations

import json
from pathlib import Path

import typer

from .harness.ledger import load_implementation_ledger

app = typer.Typer(no_args_is_help=True, help="Validate and inspect the implementation ledger")


@app.command("validate")
def validate_ledger(
    ledger_file: Path = typer.Argument(
        Path("docs/implementation-ledger.yaml"),
        exists=True,
        readable=True,
    ),
) -> None:
    ledger = load_implementation_ledger(ledger_file)
    typer.echo(
        json.dumps(
            {
                "valid": True,
                "project": ledger.project,
                "module_count": len(ledger.modules),
                "counts": ledger.counts(),
                "unfinished": [item.module_id for item in ledger.unfinished()],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


@app.command("status")
def ledger_status(
    ledger_file: Path = typer.Argument(
        Path("docs/implementation-ledger.yaml"),
        exists=True,
        readable=True,
    ),
) -> None:
    ledger = load_implementation_ledger(ledger_file)
    for module in ledger.modules:
        typer.echo(f"{module.status.value:12} {module.module_id:24} {module.title}")


if __name__ == "__main__":
    app()
