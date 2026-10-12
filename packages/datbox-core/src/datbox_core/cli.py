"""The `dat` root command."""

from __future__ import annotations

import typer

from datbox_core import __version__
from datbox_core.plugins import discover

app = typer.Typer(
    name="dat",
    help="dat: the Data Analyst Toolbox. Portable, zero-infrastructure utilities for analysts.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"dat {__version__}")
        raise typer.Exit()


@app.callback()
def root(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show the dat version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Root callback; subcommands are supplied by installed datbox-* plugins."""


@app.command()
def plugins() -> None:
    """List installed dat modules and report any that failed to load."""
    loaded, failed = discover()
    if not loaded and not failed:
        typer.echo("No plugins installed. Try: pip install datbox-viz")
        return
    for plugin in loaded:
        dist = f" ({plugin.distribution})" if plugin.distribution else ""
        typer.echo(f"  {plugin.name}{dist}")
    for broken in failed:
        typer.secho(f"  {broken.name}  FAILED: {broken.error}", fg=typer.colors.RED, err=True)
    if failed:
        raise typer.Exit(code=1)


def build_app() -> typer.Typer:
    """Attach every discovered plugin to the root app and return it."""
    loaded, _failed = discover()
    for plugin in loaded:
        app.add_typer(plugin.app, name=plugin.name)
    return app


def main() -> None:
    """Console-script entry point."""
    build_app()()


if __name__ == "__main__":
    main()
