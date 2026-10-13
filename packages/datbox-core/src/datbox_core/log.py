"""Logging for dat commands: one ``dat`` logger namespace, stderr, no surprises.

Modules call ``log = get_logger(__name__)`` at import time and never configure
handlers. The CLI calls :func:`configure` once; libraries embedding dat can call
it too or attach their own handlers to the ``dat`` logger.

Level resolution: an explicit ``level`` argument → ``$DAT_LOG_LEVEL`` → ``INFO``.
"""

from __future__ import annotations

import logging
import os
import sys

LOG_LEVEL_ENV = "DAT_LOG_LEVEL"
ROOT_NAME = "dat"

_FORMAT = "%(levelname)-7s %(name)s: %(message)s"
_configured = False


class _StderrHandler(logging.StreamHandler):  # type: ignore[type-arg]
    """Writes to whatever ``sys.stderr`` is *now*, so redirection and capture both work."""

    def __init__(self) -> None:
        super().__init__()

    @property
    def stream(self):  # type: ignore[override]
        return sys.stderr

    @stream.setter
    def stream(self, value) -> None:
        pass


def get_logger(name: str | None = None) -> logging.Logger:
    """A child of the ``dat`` logger. ``datbox_viz.build`` becomes ``dat.viz.build``."""
    if not name:
        return logging.getLogger(ROOT_NAME)
    for prefix in ("datbox_core.", "datbox_"):
        if name.startswith(prefix):
            name = name[len(prefix) :]
            break
    return logging.getLogger(f"{ROOT_NAME}.{name}")


def configure(
    level: int | str | None = None, *, verbose: bool = False, quiet: bool = False
) -> None:
    """Attach a stderr handler to the ``dat`` logger (idempotent) and set its level."""
    global _configured
    root = logging.getLogger(ROOT_NAME)
    if not _configured:
        handler = _StderrHandler()
        handler.setFormatter(logging.Formatter(_FORMAT))
        root.addHandler(handler)
        root.propagate = False
        _configured = True
    root.setLevel(resolve_level(level, verbose=verbose, quiet=quiet))


def resolve_level(
    level: int | str | None = None, *, verbose: bool = False, quiet: bool = False
) -> int:
    """The effective level given flags and ``$DAT_LOG_LEVEL``; flags win over the env."""
    if quiet:
        return logging.WARNING
    if verbose:
        return logging.DEBUG
    if level is None:
        level = os.environ.get(LOG_LEVEL_ENV, "INFO")
    if isinstance(level, int):
        return level
    numeric = logging.getLevelName(level.upper())
    return numeric if isinstance(numeric, int) else logging.INFO
