"""`dat viz` subcommands. Registered with datbox-core through the ``datbox.plugins`` entry point."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from datbox_viz.spec import json_schema, load_spec

app = typer.Typer(help="Single-file HTML dashboards from a YAML spec.", no_args_is_help=True)


@app.command()
def validate(
    spec: Annotated[
        Path, typer.Argument(exists=True, dir_okay=False, help="Dashboard spec (YAML).")
    ],
    check_sources: Annotated[
        bool,
        typer.Option("--check-sources/--no-check-sources", help="Also verify source files exist."),
    ] = True,
) -> None:
    """Validate a dashboard spec and summarise what it would embed."""
    dash = load_spec(spec)
    typer.echo(
        f"ok: {dash.title!r} — {len(dash.components)} components, {len(dash.filters)} filters"
    )
    for name, fields in dash.fields_by_source().items():
        src = dash.sources[name]
        status = ""
        if check_sources:
            status = "  [found]" if src.path.is_file() else "  [MISSING]"
        typer.echo(f"  {name}: {src.type} {src.path}{status}")
        typer.echo(f"    embeds {len(fields)} columns: {', '.join(sorted(fields))}")


@app.command()
def schema() -> None:
    """Print the JSON Schema for dashboard specs (for editors and the builder)."""
    typer.echo(json.dumps(json_schema(), indent=2))
