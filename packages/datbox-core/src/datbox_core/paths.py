"""Where dat looks for its files.

Two locations, in override order (later wins):

1. **User profiles** — ``$XDG_CONFIG_HOME/dat/profiles.yml`` (default
   ``~/.config/dat/profiles.yml``). ``DAT_CONFIG_DIR`` replaces the directory
   outright, which is how tests and unusual corporate setups point dat elsewhere.
2. **Project file** — ``dat.yml`` in the current directory or the nearest parent
   (stopping at the filesystem root or the home directory). Same schema; its
   profiles are merged over the user profiles of the same name.
"""

from __future__ import annotations

import os
from pathlib import Path

CONFIG_DIR_ENV = "DAT_CONFIG_DIR"
PROFILE_ENV = "DAT_PROFILE"
PROFILES_FILENAME = "profiles.yml"
PROJECT_FILENAME = "dat.yml"


def config_dir() -> Path:
    """The user-level dat config directory (not created)."""
    override = os.environ.get(CONFIG_DIR_ENV)
    if override:
        return Path(override).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / "dat"


def user_profiles_path() -> Path:
    """Path of the user profiles file, whether or not it exists."""
    return config_dir() / PROFILES_FILENAME


def find_project_file(start: Path | None = None) -> Path | None:
    """Find ``dat.yml`` in ``start`` (default: cwd) or the nearest parent.

    The walk stops after checking the home directory or the filesystem root,
    so a stray file two levels above a home directory is never picked up.
    """
    here = (start or Path.cwd()).resolve()
    home = Path.home().resolve()
    for directory in (here, *here.parents):
        candidate = directory / PROJECT_FILENAME
        if candidate.is_file():
            return candidate
        if directory == home:
            break
    return None


def expand(path: str | Path) -> Path:
    """Expand ``~`` and ``$VARS`` in a path without resolving symlinks."""
    return Path(os.path.expandvars(str(path))).expanduser()
