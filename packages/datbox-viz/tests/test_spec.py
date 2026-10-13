from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from datbox_core.errors import ConfigError
from datbox_viz import spec as vz
from datbox_viz.cli import app

runner = CliRunner()

MINIMAL = {
    "title": "T",
    "sources": {"s": {"type": "csv", "path": "x.csv"}},
    "components": [
        {"id": "k", "type": "kpi", "title": "K", "measure": {"field": "v", "agg": "sum"}}
    ],
}


def variant(**changes: object) -> dict[str, object]:
    base: dict[str, object] = yaml.safe_load(yaml.safe_dump(MINIMAL))
    base.update(changes)
    return base


def test_prototype_spec_loads(spec_dir: Path) -> None:
    dash = vz.load_spec(spec_dir / "dashboard.yml")
    assert dash.spec_version == 1
    assert [c.type for c in dash.components] == ["kpi", "kpi", "kpi", "bar", "line", "pie", "table"]
    assert dash.sources["orders"].path == spec_dir / "orders.parquet"  # anchored at the spec
    assert all(c.source == "orders" for c in dash.components)
    assert all(f.source == "orders" for f in dash.filters)
    bar = dash.component("rev_by_region")
    assert isinstance(bar, vz.Bar) and bar.sort == "desc" and bar.grid.h == 320


def test_fields_by_source_is_exactly_what_the_page_needs(spec_dir: Path) -> None:
    dash = vz.load_spec(spec_dir / "dashboard.yml")
    fields = dash.fields_by_source()["orders"]
    assert fields == {
        "order_id", "order_date", "region", "product_line", "rep", "units", "revenue", "month",
    }  # fmt: skip
    assert "unused_column" not in fields
    # the embedded columns really are a subset of the source
    embedded = dash.sources["orders"].load().select(sorted(fields)).collect()
    assert embedded.width == len(fields)


def test_round_trip_through_yaml(spec_dir: Path) -> None:
    dash = vz.load_spec(spec_dir / "dashboard.yml")
    again = vz.Dashboard.from_yaml(dash.to_yaml())
    assert again == dash
    assert "null" not in dash.to_yaml()


def test_minimal_defaults() -> None:
    dash = vz.Dashboard.model_validate(MINIMAL)
    assert dash.layout.columns == 12 and dash.components[0].grid.w == 12
    assert dash.components[0].source == "s"
    assert dash.fields_by_source() == {"s": {"v"}}


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        ("revenue / units", "looks like an expression"),
        ("sum(revenue)", "looks like an expression"),
        (" revenue", "non-empty column name"),
        ("", "non-empty column name"),
    ],
)
def test_fields_are_columns_not_expressions(bad: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        vz.Measure(field=bad)


def test_column_names_may_contain_spaces_and_hyphens() -> None:
    assert vz.Dimension(field="Product Line-2").field == "Product Line-2"


def test_unknown_agg_type_and_keys() -> None:
    with pytest.raises(ValueError, match="agg"):
        vz.Measure.model_validate({"field": "v", "agg": "median"})
    with pytest.raises(ValueError, match="extra"):
        vz.Measure.model_validate({"field": "v", "window": "7d"})
    with pytest.raises(ValueError, match="type"):
        vz.Dashboard.model_validate(
            variant(components=[{"id": "h", "type": "heatmap", "title": "H"}])
        )


def test_duplicate_ids_and_bad_ids() -> None:
    comp = {"id": "k", "type": "kpi", "title": "K", "measure": {"field": "v"}}
    with pytest.raises(ValueError, match="duplicate component id"):
        vz.Dashboard.model_validate(variant(components=[comp, comp]))
    with pytest.raises(ValueError, match="pattern"):
        vz.Dashboard.model_validate(variant(components=[{**comp, "id": "Bad-Id"}]))


def test_multiple_sources_require_explicit_source() -> None:
    two = {
        "a": {"type": "csv", "path": "a.csv"},
        "b": {"type": "parquet", "path": "b.parquet"},
    }
    with pytest.raises(ValueError, match="'source' is required"):
        vz.Dashboard.model_validate(variant(sources=two))
    comp = {**MINIMAL["components"][0], "source": "b"}  # type: ignore[index]
    dash = vz.Dashboard.model_validate(
        variant(sources=two, components=[comp], filters=[{"field": "f", "source": "a"}])
    )
    assert dash.fields_by_source() == {"a": {"f"}, "b": {"v"}}
    with pytest.raises(ValueError, match="unknown source 'zz'"):
        vz.Dashboard.model_validate(variant(sources=two, components=[{**comp, "source": "zz"}]))


def test_grid_width_within_layout() -> None:
    comp = {**MINIMAL["components"][0], "grid": {"w": 13}}  # type: ignore[index]
    with pytest.raises(ValueError, match=r"exceeds layout\.columns"):
        vz.Dashboard.model_validate(variant(components=[comp]))
    assert vz.Dashboard.model_validate(variant(components=[comp], layout={"columns": 16}))


def test_line_series_must_differ_from_x() -> None:
    with pytest.raises(ValueError, match="series field must differ"):
        vz.Line(
            id="l", type="line", title="L",
            x=vz.Dimension(field="m"), y=vz.Measure(field="v"), series=vz.Dimension(field="m"),
        )  # fmt: skip


def test_table_sort_must_be_a_column() -> None:
    with pytest.raises(ValueError, match="not one of the table's columns"):
        vz.Table(
            id="t", type="table", title="T",
            columns=[vz.Column(field="a")], sort=vz.TableSort(field="b"),
        )  # fmt: skip


def test_load_spec_errors_are_config_errors(tmp_path: Path, sales_spec: str) -> None:
    f = tmp_path / "d.yml"
    f.write_text("title: [\n")
    with pytest.raises(ConfigError, match="invalid YAML"):
        vz.load_spec(f)
    f.write_text("- a list\n")
    with pytest.raises(ConfigError, match="must be a mapping"):
        vz.load_spec(f)
    f.write_text(sales_spec.replace("agg: sum", "agg: median", 1))
    with pytest.raises(ConfigError, match=r"components\.0\.measure\.agg"):
        vz.load_spec(f)
    with pytest.raises(ConfigError, match="cannot read"):
        vz.load_spec(tmp_path / "missing.yml")


def test_json_schema_has_every_component_type() -> None:
    schema = vz.json_schema()
    assert set(schema["$defs"]) >= {"KPI", "Bar", "Line", "Pie", "Table", "Measure", "Dimension"}
    assert schema["properties"]["spec_version"]["const"] == 1


def test_cli_validate_and_schema(spec_dir: Path) -> None:
    result = runner.invoke(app, ["validate", str(spec_dir / "dashboard.yml")])
    assert result.exit_code == 0, result.output
    assert "7 components, 2 filters" in result.output
    assert "[found]" in result.output and "embeds 8 columns" in result.output

    result = runner.invoke(app, ["schema"])
    assert result.exit_code == 0 and '"spec_version"' in result.output
