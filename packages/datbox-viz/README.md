# datbox-viz

Single-file HTML dashboards from a YAML spec and the tables you already have
(DuckDB, Parquet, CSV). The output opens from a file share with networking off:
no server, no viewer licence, no IT ticket.

**Status: the spec is here; the generator is next.** Today `datbox-viz` ships the
dashboard spec (`datbox_viz.spec`), `dat viz validate`, and `dat viz schema`.
`dat viz build` lands in v0.1 (gate 2026-11-17).

```bash
pip install datbox-viz
dat viz validate dashboard.yml
dat viz schema > dashboard.schema.json   # JSON Schema for your editor
```

## The spec

```yaml
spec_version: 1
title: Sales Overview
sources:
  orders: { type: duckdb, path: ~/dbt/target/dev.duckdb, table: fct_orders }
filters:
  - { field: region }
components:
  - { id: kpi_revenue, type: kpi, title: Total revenue,
      measure: { field: revenue, agg: sum }, format: currency, grid: { w: 4 } }
  - { id: rev_by_region, type: bar, title: Revenue by region,
      x: { field: region }, y: { field: revenue, agg: sum }, sort: desc, grid: { w: 8, h: 320 } }
```

Component types: `kpi`, `bar`, `line`, `pie`, `table`. Aggregations: `sum`, `count`,
`mean`, `min`, `max`. Formats: `currency`, `integer`, `number`, `percent`. Layout is a
grid (`layout.columns`, default 12); each component takes `grid: { w, h }`.

## What the page computes, and what it does not

Every number comes from a SQL query at build time — a source *is* that query, or a
file dbt already built. The generator embeds the resulting rows (only the columns the
spec references) in the HTML. At view time the page re-slices those rows by the declared
filters and re-applies the declared aggregations, so cross-filtering works without a
server. That is all the page does. A `field` names a column; the spec cannot express a
calculated field, a ratio, or a window. If the number you want is not a column, it
belongs in the query or in dbt (ADR-016). The v0.3 builder edits this same file, so it
can offer nothing the file cannot say.

## Data awareness

The HTML file contains its data. Treat it with the same care as the data inside it.
