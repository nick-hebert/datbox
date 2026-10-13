"""The `dat` root command."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from datbox_core import __version__, log
from datbox_core.config import EXAMPLE_PROFILES, load_config
from datbox_core.errors import DatError
from datbox_core.paths import PROFILE_ENV, find_project_file, user_profiles_path
from datbox_core.plugins import discover
from datbox_core.secrets import conventional_refs, keyring_available

app = typer.Typer(
    name="dat",
    help="dat: the Data Analyst Toolbox. Portable, zero-infrastructure utilities for analysts.",
    no_args_is_help=True,
    add_completion=False,
)
config_app = typer.Typer(help="Inspect and initialise dat profiles.", no_args_is_help=True)
app.add_typer(config_app, name="config")


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
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Debug logging."),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Warnings and errors only."),
) -> None:
    """Root callback; subcommands are supplied by installed datbox-* plugins."""
    log.configure(verbose=verbose, quiet=quiet)


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


@config_app.command("paths")
def config_paths() -> None:
    """Show where dat looks for config and which files exist."""
    user = user_profiles_path()
    project = find_project_file()
    typer.echo(f"user profiles:   {user}  [{'found' if user.is_file() else 'missing'}]")
    typer.echo(f"project dat.yml: {project or '(none found from ' + str(Path.cwd()) + ')'}")
    typer.echo(f"keyring backend: {'available' if keyring_available() else 'not installed'}")


@config_app.command("show")
def config_show(
    profile: str | None = typer.Option(None, "--profile", "-p", envvar=PROFILE_ENV),
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Show the resolved profile. Secret locations are shown; secret values never are."""
    config = load_config()
    selected = config.select(profile)
    if as_json:
        typer.echo(json.dumps(selected.model_dump(mode="json"), indent=2))
        return
    desc = f" — {selected.description}" if selected.description else ""
    others = sorted(n for n in config.profiles if n != selected.name)
    typer.echo(f"profile: {selected.name}{desc}")
    typer.echo(f"files:   {', '.join(str(p) for p in config.files) or '(none)'}")
    typer.echo(f"others:  {', '.join(others) or '(none)'}")
    typer.echo("sources:")
    for name, src in sorted(selected.sources.items()):
        detail = getattr(src, "table", None) or getattr(src, "query", None)
        typer.echo(f"  {name:<16} {src.type:<8} {src.path}" + (f"  ({detail})" if detail else ""))
    if not selected.sources:
        typer.echo("  (none)")
    typer.echo("secrets:")
    for name, ref in sorted(selected.secrets.items()):
        typer.echo(f"  {name:<16} {ref.describe()}")
    if not selected.secrets:
        tried = " → ".join(r.describe() for r in conventional_refs("name", selected.name))
        typer.echo(f"  (none declared; convention: {tried})")
    typer.echo("settings:")
    for key, block in sorted(selected.settings.items()):
        typer.echo(f"  {key}: {', '.join(sorted(block)) or '{}'}")
    if not selected.settings:
        typer.echo("  (none)")


@config_app.command("init")
def config_init(
    force: bool = typer.Option(False, "--force", help="Overwrite an existing file."),
) -> None:
    """Create a starter profiles.yml in the user config directory."""
    target = user_profiles_path()
    if target.exists() and not force:
        raise DatError(f"{target} already exists; use --force to overwrite")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(EXAMPLE_PROFILES, encoding="utf-8")
    typer.echo(f"wrote {target}")


def build_app() -> typer.Typer:
    """Attach every discovered plugin to the root app and return it."""
    loaded, _failed = discover()
    for plugin in loaded:
        app.add_typer(plugin.app, name=plugin.name)
    return app


def main() -> None:
    """Console-script entry point. dat's own errors print cleanly; bugs still traceback."""
    try:
        build_app()()
    except DatError as exc:
        typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
