"""The dashboard spec: the contract between the author, the generator, and the builder.

A dashboard is one YAML file. ``dat viz build`` compiles it to a single HTML file
(ADR-003/004); the v0.3 builder (ADR-015) is a GUI that edits this same file and
nothing else. Every key here is therefore a *stable* name: additions are fine,
renames and removals bump ``spec_version``.

Shape (``spec_version: 1``)::

    spec_version: 1
    title: Sales Overview
    subtitle: FY2026 · seeded fake data
    sources:                      # datbox-core sources; every one is embedded
      orders: { type: duckdb, path: ~/dbt/target/dev.duckdb, table: fct_orders }
    filters:                      # global dimension filters, one row of controls
      - { field: region }
      - { field: product_line, label: Product line }
    layout: { columns: 12 }
    components:
      - { id: kpi_revenue, type: kpi, title: Total revenue,
          measure: { field: revenue, agg: sum }, format: currency, grid: { w: 4 } }
      - { id: rev_by_region, type: bar, title: Revenue by region,
          x: { field: region }, y: { field: revenue, agg: sum },
          format: currency, sort: desc, grid: { w: 6, h: 320 } }
      - { id: rev_by_month, type: line, title: Monthly revenue by line,
          x: { field: month }, y: { field: revenue, agg: sum },
          series: { field: product_line }, format: currency, grid: { w: 6, h: 320 } }
      - { id: rev_share, type: pie, title: Revenue share,
          category: { field: product_line }, value: { field: revenue, agg: sum },
          format: currency, grid: { w: 4, h: 320 } }
      - { id: orders_table, type: table, title: Orders,
          columns: [ { field: order_id, label: Order },
                     { field: revenue, label: Revenue, format: currency } ],
          sort: { field: order_id, dir: desc }, page_size: 25, grid: { w: 8, h: 320 } }

**What the page does with the embedded rows (ADR-016, ADR-017).** Every number on
a dat dashboard comes from a SQL query run at build time: a source *is* that
query (or a file dbt already built). The generator embeds the resulting rows —
only the columns the spec references — as JSON in the HTML. At view time the page
*re-slices* those embedded rows by the declared ``filters`` and re-applies the
declared aggregations (``sum``, ``count``, ``mean``, ``min``, ``max``) so that
cross-filtering works in a file with no server behind it. That is the whole of
what the page computes. The spec cannot express a calculated field, a ratio of
two measures, a window, or any expression: a ``field`` names a column of the
embedded rows, and if the number you want is not a column, it belongs in the SQL
(or in dbt), not here. The same rule binds the builder: it edits this file, so it
cannot offer anything this file cannot say.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from datbox_core.errors import ConfigError
from datbox_core.sources import Source

SPEC_VERSION = 1

Agg = Literal["sum", "count", "mean", "min", "max"]
"""Aggregations the page can re-apply when it re-slices embedded rows."""

Format = Literal["currency", "integer", "number", "percent"]
"""Display formats the renderer knows. Applies to a measure's values."""

SortDir = Literal["asc", "desc"]

_ID = r"^[a-z][a-z0-9_]*$"
_EXPRESSION_CHARS = re.compile(r"[()+*/<>=]")


def _check_column_name(value: str) -> str:
    """A field is a column name, never an expression (ADR-016)."""
    if value != value.strip() or not value:
        raise ValueError("field must be a non-empty column name")
    if _EXPRESSION_CHARS.search(value):
        raise ValueError(
            f"field {value!r} looks like an expression; a field names a column of the source. "
            "Put calculations in the source query or in dbt (ADR-016)."
        )
    return value


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Dimension(_Strict):
    """A column whose distinct values become categories, axis ticks, or series."""

    field: str

    _check = field_validator("field")(_check_column_name)


class Measure(_Strict):
    """A column plus the aggregation the page applies to it."""

    field: str
    agg: Agg = "sum"

    _check = field_validator("field")(_check_column_name)


class Filter(_Strict):
    """A global filter over one column; rendered as a select, also set by chart clicks."""

    field: str
    label: str | None = None
    source: str | None = Field(default=None, description="Defaults to the only source.")

    _check = field_validator("field")(_check_column_name)


class Grid(_Strict):
    """Placement in the layout grid: width in columns, height in pixels."""

    w: int = Field(default=12, ge=1)
    h: int | None = Field(default=None, ge=120, le=2000)


class Layout(_Strict):
    columns: int = Field(default=12, ge=1, le=24)


class _Component(_Strict):
    id: str = Field(pattern=_ID)
    title: str
    source: str | None = Field(default=None, description="Defaults to the only source.")
    grid: Grid = Field(default_factory=Grid)
    format: Format | None = None

    def fields(self) -> set[str]:  # pragma: no cover - overridden
        """Every column this component reads from its source."""
        raise NotImplementedError


class KPI(_Component):
    type: Literal["kpi"]
    measure: Measure

    def fields(self) -> set[str]:
        return {self.measure.field}


class Bar(_Component):
    type: Literal["bar"]
    x: Dimension
    y: Measure
    sort: Literal["asc", "desc", "x"] = Field(
        default="x", description="'x' sorts by category; asc/desc by the measure."
    )

    def fields(self) -> set[str]:
        return {self.x.field, self.y.field}


class Line(_Component):
    type: Literal["line"]
    x: Dimension
    y: Measure
    series: Dimension | None = None

    @model_validator(mode="after")
    def _series_differs_from_x(self) -> Line:
        if self.series is not None and self.series.field == self.x.field:
            raise ValueError("series field must differ from x field")
        return self

    def fields(self) -> set[str]:
        out = {self.x.field, self.y.field}
        if self.series:
            out.add(self.series.field)
        return out


class Pie(_Component):
    type: Literal["pie"]
    category: Dimension
    value: Measure

    def fields(self) -> set[str]:
        return {self.category.field, self.value.field}


class Column(_Strict):
    field: str
    label: str | None = None
    format: Format | None = None

    _check = field_validator("field")(_check_column_name)


class TableSort(_Strict):
    field: str
    dir: SortDir = "asc"


class Table(_Component):
    type: Literal["table"]
    columns: list[Column] = Field(min_length=1)
    sort: TableSort | None = None
    page_size: int = Field(default=25, ge=1, le=500)
    searchable: bool = True

    @model_validator(mode="after")
    def _sort_is_a_column(self) -> Table:
        if self.sort and self.sort.field not in {c.field for c in self.columns}:
            raise ValueError(f"sort field {self.sort.field!r} is not one of the table's columns")
        return self

    def fields(self) -> set[str]:
        return {c.field for c in self.columns}


Component = Annotated[KPI | Bar | Line | Pie | Table, Field(discriminator="type")]
COMPONENT_TYPES: tuple[str, ...] = ("kpi", "bar", "line", "pie", "table")


class Dashboard(_Strict):
    """One dashboard. See the module docstring for the YAML shape and the rules."""

    spec_version: Literal[1] = SPEC_VERSION
    title: str = Field(min_length=1)
    subtitle: str | None = None
    sources: dict[str, Source] = Field(min_length=1)
    filters: list[Filter] = Field(default_factory=list)
    layout: Layout = Field(default_factory=Layout)
    components: list[Component] = Field(min_length=1)

    @field_validator("sources")
    @classmethod
    def _source_names(cls, value: dict[str, Source]) -> dict[str, Source]:
        for name in value:
            if not re.match(_ID, name):
                raise ValueError(f"source name {name!r} must match {_ID}")
        return value

    @model_validator(mode="after")
    def _cross_checks(self) -> Dashboard:
        only = next(iter(self.sources)) if len(self.sources) == 1 else None
        seen: set[str] = set()
        for comp in self.components:
            if comp.id in seen:
                raise ValueError(f"duplicate component id {comp.id!r}")
            seen.add(comp.id)
            comp.source = self._resolve_source(comp.source, only, f"component {comp.id!r}")
            if comp.grid.w > self.layout.columns:
                raise ValueError(
                    f"component {comp.id!r}: grid.w {comp.grid.w} exceeds layout.columns "
                    f"{self.layout.columns}"
                )
        for flt in self.filters:
            flt.source = self._resolve_source(flt.source, only, f"filter {flt.field!r}")
        return self

    def _resolve_source(self, name: str | None, only: str | None, what: str) -> str:
        if name is None:
            if only is None:
                raise ValueError(
                    f"{what}: 'source' is required when a dashboard declares several sources "
                    f"({', '.join(self.sources)})"
                )
            return only
        if name not in self.sources:
            raise ValueError(
                f"{what}: unknown source {name!r}; declared: {', '.join(self.sources)}"
            )
        return name

    # ---- what the generator needs -------------------------------------------------

    def fields_by_source(self) -> dict[str, set[str]]:
        """Columns to embed per source: the union of what components and filters reference.

        The generator projects each source to exactly these columns before embedding,
        so the HTML carries no column the dashboard does not use.
        """
        out: dict[str, set[str]] = defaultdict(set)
        for comp in self.components:
            out[comp.source or ""].update(comp.fields())
        for flt in self.filters:
            out[flt.source or ""].add(flt.field)
        return {name: out.get(name, set()) for name in self.sources}

    def component(self, component_id: str) -> Component:
        for comp in self.components:
            if comp.id == component_id:
                return comp
        raise KeyError(component_id)

    # ---- round-tripping (the builder loads, edits, and saves this file) ---------------

    def to_yaml(self) -> str:
        """Serialise back to YAML with ``None`` dropped and key order preserved."""
        data = self.model_dump(mode="json", exclude_none=True)
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)

    @classmethod
    def from_yaml(cls, text: str, *, base: Path | None = None) -> Dashboard:
        """Parse YAML text. Relative source paths anchor at ``base`` when given."""
        try:
            raw = yaml.safe_load(text) or {}
        except yaml.YAMLError as exc:
            raise ConfigError(f"invalid YAML: {exc}") from None
        if not isinstance(raw, dict):
            raise ConfigError("a dashboard spec must be a mapping")
        try:
            dash = cls.model_validate(raw)
        except ValidationError as exc:
            raise ConfigError(format_errors(exc)) from None
        if base is not None:
            dash.sources = {k: s.with_base(base) for k, s in dash.sources.items()}
        return dash


def load_spec(path: str | Path) -> Dashboard:
    """Read a dashboard spec file; relative source paths anchor at the spec's directory."""
    spec_path = Path(path)
    try:
        text = spec_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot read {spec_path}: {exc.strerror}") from None
    try:
        return Dashboard.from_yaml(text, base=spec_path.resolve().parent)
    except ConfigError as exc:
        raise ConfigError(f"{spec_path}: {exc}") from None


def json_schema() -> dict[str, Any]:
    """JSON Schema for the spec — for editors and for the builder's own validation."""
    return Dashboard.model_json_schema()


def format_errors(exc: ValidationError) -> str:
    """Pydantic errors as 'where: what' lines, with discriminated-union noise removed."""
    lines: list[str] = []
    for err in exc.errors():
        loc = [str(p) for p in err["loc"] if str(p) not in COMPONENT_TYPES]
        lines.append(f"{'.'.join(loc) or '<root>'}: {err['msg']}")
    return "\n".join(dict.fromkeys(lines))
