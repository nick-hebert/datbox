"""Output writers: one call to land a Polars frame as Parquet, CSV, or a DuckDB table.

Every extractor and transformer ends with ``write(frame, path)``. The format is
inferred from the suffix (``.parquet`` / ``.csv`` / ``.duckdb`` / ``.db``) or
given explicitly. ``mode="append"`` adds rows where the format allows it (CSV,
DuckDB); Parquet is replace-only because appending to one file is not a thing.

DuckDB targets need a table name; it defaults to the file's stem.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

import polars as pl

from datbox_core.errors import DatError
from datbox_core.log import get_logger

log = get_logger(__name__)

Format = Literal["parquet", "csv", "duckdb"]
Mode = Literal["replace", "append"]

_SUFFIXES: dict[str, Format] = {
    ".parquet": "parquet",
    ".pq": "parquet",
    ".csv": "csv",
    ".duckdb": "duckdb",
    ".ddb": "duckdb",
    ".db": "duckdb",
}
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class WriteResult:
    """What a writer produced, for logging and for CLIs to print."""

    path: Path
    format: Format
    rows: int
    table: str | None = None

    def __str__(self) -> str:
        where = f"{self.path}" + (f" (table {self.table})" if self.table else "")
        return f"wrote {self.rows:,} rows → {where}"


class Writer(Protocol):
    """A writer knows one format. ``write`` returns what it did."""

    format: Format

    def write(
        self,
        frame: pl.DataFrame | pl.LazyFrame,
        path: Path,
        *,
        mode: Mode = "replace",
        table: str | None = None,
    ) -> WriteResult: ...


class ParquetWriter:
    format: Format = "parquet"

    def write(
        self,
        frame: pl.DataFrame | pl.LazyFrame,
        path: Path,
        *,
        mode: Mode = "replace",
        table: str | None = None,
    ) -> WriteResult:
        if mode == "append":
            raise DatError("Parquet does not support append; write a new file or use duckdb")
        df = _collect(frame)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(path)
        return WriteResult(path, "parquet", df.height)


class CSVWriter:
    format: Format = "csv"

    def write(
        self,
        frame: pl.DataFrame | pl.LazyFrame,
        path: Path,
        *,
        mode: Mode = "replace",
        table: str | None = None,
    ) -> WriteResult:
        df = _collect(frame)
        path.parent.mkdir(parents=True, exist_ok=True)
        if mode == "append" and path.exists() and path.stat().st_size > 0:
            with path.open("ab") as fh:
                df.write_csv(fh, include_header=False)
        else:
            df.write_csv(path)
        return WriteResult(path, "csv", df.height)


class DuckDBWriter:
    format: Format = "duckdb"

    def write(
        self,
        frame: pl.DataFrame | pl.LazyFrame,
        path: Path,
        *,
        mode: Mode = "replace",
        table: str | None = None,
    ) -> WriteResult:
        import duckdb

        table = table or path.stem
        if not _IDENT.match(table):
            raise DatError(f"invalid DuckDB table name {table!r}")
        df = _collect(frame)
        path.parent.mkdir(parents=True, exist_ok=True)
        con = duckdb.connect(str(path))
        try:
            con.register("_dat_frame", df.to_arrow())
            if mode == "append":
                con.execute(
                    f'CREATE TABLE IF NOT EXISTS "{table}" AS SELECT * FROM _dat_frame LIMIT 0'
                )
                con.execute(f'INSERT INTO "{table}" SELECT * FROM _dat_frame')
            else:
                con.execute(f'CREATE OR REPLACE TABLE "{table}" AS SELECT * FROM _dat_frame')
            con.unregister("_dat_frame")
        finally:
            con.close()
        return WriteResult(path, "duckdb", df.height, table)


WRITERS: dict[Format, Writer] = {
    "parquet": ParquetWriter(),
    "csv": CSVWriter(),
    "duckdb": DuckDBWriter(),
}


def infer_format(path: Path) -> Format:
    """Format from the file suffix, or ``DatError`` naming the suffixes dat knows."""
    try:
        return _SUFFIXES[path.suffix.lower()]
    except KeyError:
        known = ", ".join(sorted(_SUFFIXES))
        raise DatError(f"cannot infer output format from {path.name!r}; known: {known}") from None


def writer_for(fmt: Format) -> Writer:
    return WRITERS[fmt]


def write(
    frame: pl.DataFrame | pl.LazyFrame,
    path: str | Path,
    *,
    format: Format | None = None,
    mode: Mode = "replace",
    table: str | None = None,
) -> WriteResult:
    """Write ``frame`` to ``path`` in ``format`` (inferred from the suffix when omitted)."""
    target = Path(path)
    fmt = format or infer_format(target)
    result = writer_for(fmt).write(frame, target, mode=mode, table=table)
    log.info("%s", result)
    return result


def _collect(frame: pl.DataFrame | pl.LazyFrame) -> pl.DataFrame:
    return frame.collect() if isinstance(frame, pl.LazyFrame) else frame
