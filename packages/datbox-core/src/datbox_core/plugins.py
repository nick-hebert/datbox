"""Plugin discovery for `dat` subcommands.

Any installed distribution can register a Typer app under the ``datbox.plugins``
entry-point group. The entry-point *name* becomes the subcommand name and the
*value* must resolve to a ``typer.Typer`` instance.

Example ``pyproject.toml`` for a module::

    [project.entry-points."datbox.plugins"]
    viz = "datbox_viz.cli:app"

Modules never import each other; they only depend on ``datbox-core``.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import EntryPoint, entry_points

import typer

PLUGIN_GROUP = "datbox.plugins"


@dataclass(frozen=True)
class LoadedPlugin:
    """A successfully loaded plugin subcommand."""

    name: str
    app: typer.Typer
    distribution: str | None


@dataclass(frozen=True)
class FailedPlugin:
    """A plugin that was found but could not be loaded."""

    name: str
    error: str


def discover() -> tuple[list[LoadedPlugin], list[FailedPlugin]]:
    """Find and load every registered plugin.

    A plugin that fails to import never breaks the root CLI; it is reported
    instead so the user can see what is broken.
    """
    loaded: list[LoadedPlugin] = []
    failed: list[FailedPlugin] = []
    for ep in _iter_entry_points():
        try:
            obj = ep.load()
        except Exception as exc:
            failed.append(FailedPlugin(name=ep.name, error=f"{type(exc).__name__}: {exc}"))
            continue
        if not isinstance(obj, typer.Typer):
            failed.append(
                FailedPlugin(name=ep.name, error=f"entry point is {type(obj).__name__}, not Typer")
            )
            continue
        dist = ep.dist.name if ep.dist is not None else None
        loaded.append(LoadedPlugin(name=ep.name, app=obj, distribution=dist))
    return loaded, failed


def _iter_entry_points() -> list[EntryPoint]:
    return sorted(entry_points(group=PLUGIN_GROUP), key=lambda ep: ep.name)
