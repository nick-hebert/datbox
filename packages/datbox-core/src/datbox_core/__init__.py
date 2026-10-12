"""datbox-core: the `dat` CLI, plugin registry, and shared foundations."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("datbox-core")
except PackageNotFoundError:  # pragma: no cover - source checkout without install
    __version__ = "0.0.0"

__all__ = ["__version__"]
