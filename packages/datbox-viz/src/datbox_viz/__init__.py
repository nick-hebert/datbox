"""datbox-viz: YAML spec + DuckDB/Parquet/CSV -> one self-contained HTML dashboard."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("datbox-viz")
except PackageNotFoundError:  # pragma: no cover - source checkout without install
    __version__ = "0.0.0"

__all__ = ["__version__"]
