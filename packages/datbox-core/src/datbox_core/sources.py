"""Tabular sources: where a table comes from, and how to read it into Polars.

A source is a Parquet file, a CSV file, or a DuckDB database (a table or a
query). This is the one model every reader-shaped module (viz, profile, diff,
check) shares, so a ``sources:`` block means the same thing everywhere::

    sources:
      orders:   { type: parquet, path: data/orders.parquet }
      raw:      { type: csv, path: data/raw.csv, delimiter: ";" }
      marts:    { type: duckdb, path: ~/dbt/target/dev.duckdb, table: fct_orders }
      pipeline: { type: duckdb, path: ~/dbt/target/dev.duckdb,
                  query: "select * from fct_opportunities where stage <> 'Closed Lost'" }

Reading is lazy where the format allows it (``scan_parquet`` / ``scan_csv``).
DuckDB queries run eagerly and hand their Arrow result to Polars zero-copy.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import polars as pl
from pydantic import BaseModel, ConfigDict, Field, model_validator

from datbox_core.errors import ConfigError
from datbox_core.paths import expand

_IDENT = r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$"


class _SourceBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: Path = Field(description="File path; '~' and $VARS are expanded.")

    def with_base(self, base: Path) -> Source:
        """Return a copy whose relative ``path`` is anchored at ``base``."""
        path = expand(self.path)
        if not path.is_absolute():
            path = (base / path).resolve()
        return self.model_copy(update={"path": path})  # type: ignore[return-value]

    def load(self) -> pl.LazyFrame:  # pragma: no cover - overridden
        raise NotImplementedError


class ParquetSource(_SourceBase):
    """A single Parquet file (or a glob of them)."""

    type: Literal["parquet"] = "parquet"

    def load(self) -> pl.LazyFrame:
        _require_file(self.path, allow_glob=True)
        return pl.scan_parquet(self.path)


class CSVSource(_SourceBase):
    """A delimited text file."""

    type: Literal["csv"] = "csv"
    delimiter: str = Field(default=",", min_length=1, max_length=1)
    has_header: bool = True
    encoding: Literal["utf8", "utf8-lossy"] = "utf8"
    try_parse_dates: bool = True

    def load(self) -> pl.LazyFrame:
        _require_file(self.path, allow_glob=True)
        return pl.scan_csv(
            self.path,
            separator=self.delimiter,
            has_header=self.has_header,
            encoding=self.encoding,
            try_parse_dates=self.try_parse_dates,
        )


class DuckDBSource(_SourceBase):
    """A table or a query against a DuckDB database file.

    Exactly one of ``table`` / ``query`` is required. The file is opened
    read-only, so pointing dat at the DuckDB a dbt project is building is safe.
    """

    type: Literal["duckdb"] = "duckdb"
    table: str | None = Field(default=None, pattern=_IDENT)
    query: str | None = None

    @model_validator(mode="after")
    def _table_xor_query(self) -> DuckDBSource:
        if (self.table is None) == (self.query is None):
            raise ValueError("a duckdb source needs exactly one of 'table' or 'query'")
        return self

    @property
    def sql(self) -> str:
        return self.query if self.query is not None else f"SELECT * FROM {self.table}"

    def load(self) -> pl.LazyFrame:
        import duckdb

        _require_file(self.path)
        con = duckdb.connect(str(self.path), read_only=True)
        try:
            table = con.execute(self.sql).arrow()
        finally:
            con.close()
        return pl.from_arrow(table).lazy()  # type: ignore[union-attr]


Source = Annotated[ParquetSource | CSVSource | DuckDBSource, Field(discriminator="type")]
"""The source union; use this type in any model that accepts a source."""


def _require_file(path: Path, *, allow_glob: bool = False) -> None:
    if allow_glob and any(ch in str(path) for ch in "*?["):
        return
    if not path.is_file():
        raise ConfigError(f"source file not found: {path}")
