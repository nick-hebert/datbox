"""datbox: umbrella package for the Data Analyst Toolbox. See datbox-core for the CLI."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("datbox")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

__all__ = ["__version__"]
