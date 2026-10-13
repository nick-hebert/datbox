from pathlib import Path

import duckdb
import polars as pl
import pytest

from datbox_core import writers
from datbox_core.errors import DatError


def test_infer_format() -> None:
    assert writers.infer_format(Path("x.parquet")) == "parquet"
    assert writers.infer_format(Path("x.CSV")) == "csv"
    assert writers.infer_format(Path("x.duckdb")) == "duckdb"
    with pytest.raises(DatError, match="known:"):
        writers.infer_format(Path("x.xlsx"))


def test_parquet_write_creates_parents(tmp_path: Path, frame: pl.DataFrame) -> None:
    out = tmp_path / "deep" / "dir" / "f.parquet"
    result = writers.write(frame.lazy(), out)
    assert result.rows == 3 and result.format == "parquet"
    assert pl.read_parquet(out).equals(frame)
    with pytest.raises(DatError, match="append"):
        writers.write(frame, out, mode="append")


def test_csv_append_skips_header(tmp_path: Path, frame: pl.DataFrame) -> None:
    out = tmp_path / "f.csv"
    writers.write(frame, out)
    writers.write(frame, out, mode="append")
    assert pl.read_csv(out).height == 6
    assert out.read_text().count("order_id") == 1


def test_duckdb_replace_and_append(tmp_path: Path, frame: pl.DataFrame) -> None:
    db = tmp_path / "f.duckdb"
    r1 = writers.write(frame, db)  # table defaults to the stem
    assert r1.table == "f" and "table f" in str(r1)
    writers.write(frame, db, table="orders")
    writers.write(frame.head(1), db, table="orders", mode="append")
    writers.write(frame.head(2), db, table="orders")  # replace
    con = duckdb.connect(str(db), read_only=True)
    assert con.execute("select count(*) from f").fetchone() == (3,)
    assert con.execute("select count(*) from orders").fetchone() == (2,)
    con.close()


def test_duckdb_rejects_bad_table_name(tmp_path: Path, frame: pl.DataFrame) -> None:
    with pytest.raises(DatError, match="invalid DuckDB table"):
        writers.write(frame, tmp_path / "f.duckdb", table="drop table; --")


def test_explicit_format_overrides_suffix(tmp_path: Path, frame: pl.DataFrame) -> None:
    out = tmp_path / "data.bin"
    result = writers.write(frame, out, format="csv")
    assert result.format == "csv" and pl.read_csv(out).height == 3
