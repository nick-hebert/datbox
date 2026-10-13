from pathlib import Path

import duckdb
import polars as pl
import pytest
from pydantic import TypeAdapter, ValidationError

from datbox_core.errors import ConfigError
from datbox_core.sources import CSVSource, DuckDBSource, ParquetSource, Source

adapter: TypeAdapter[Source] = TypeAdapter(Source)


def test_discriminated_union_parses_each_type() -> None:
    assert isinstance(
        adapter.validate_python({"type": "parquet", "path": "x.parquet"}), ParquetSource
    )
    assert isinstance(adapter.validate_python({"type": "csv", "path": "x.csv"}), CSVSource)
    assert isinstance(
        adapter.validate_python({"type": "duckdb", "path": "x.duckdb", "table": "t"}), DuckDBSource
    )


def test_unknown_type_and_extra_keys_rejected() -> None:
    with pytest.raises(ValidationError):
        adapter.validate_python({"type": "excel", "path": "x.xlsx"})
    with pytest.raises(ValidationError):
        adapter.validate_python({"type": "csv", "path": "x.csv", "sheet": 1})


def test_duckdb_needs_table_xor_query() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        DuckDBSource(path=Path("x.duckdb"))
    with pytest.raises(ValidationError, match="exactly one"):
        DuckDBSource(path=Path("x.duckdb"), table="t", query="select 1")
    assert DuckDBSource(path=Path("x.duckdb"), table="main.t").sql == "SELECT * FROM main.t"


def test_with_base_anchors_relative_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAT_T", str(tmp_path / "env"))
    rel = ParquetSource(path=Path("data/x.parquet")).with_base(tmp_path)
    assert rel.path == (tmp_path / "data" / "x.parquet").resolve()
    assert ParquetSource(path=Path("/abs/x.parquet")).with_base(tmp_path).path == Path(
        "/abs/x.parquet"
    )
    assert (
        ParquetSource(path=Path("$DAT_T/x.parquet")).with_base(tmp_path).path
        == tmp_path / "env" / "x.parquet"
    )


def test_parquet_roundtrip(tmp_path: Path, frame: pl.DataFrame) -> None:
    frame.write_parquet(tmp_path / "f.parquet")
    out = ParquetSource(path=tmp_path / "f.parquet").load().collect()
    assert out.equals(frame)


def test_csv_delimiter(tmp_path: Path, frame: pl.DataFrame) -> None:
    frame.write_csv(tmp_path / "f.csv", separator=";")
    out = CSVSource(path=tmp_path / "f.csv", delimiter=";").load().collect()
    assert out.equals(frame)


def test_duckdb_table_and_query(tmp_path: Path, frame: pl.DataFrame) -> None:
    db = tmp_path / "f.duckdb"
    con = duckdb.connect(str(db))
    con.register("src", frame.to_arrow())
    con.execute("create table orders as select * from src")
    con.close()
    whole = DuckDBSource(path=db, table="orders").load().collect()
    assert whole.sort("order_id").equals(frame)
    west = DuckDBSource(path=db, query="select * from orders where region = 'West'").load()
    assert west.collect().height == 2


def test_missing_file_is_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        ParquetSource(path=tmp_path / "nope.parquet").load()
    with pytest.raises(ConfigError, match="not found"):
        DuckDBSource(path=tmp_path / "nope.duckdb", table="t").load()
