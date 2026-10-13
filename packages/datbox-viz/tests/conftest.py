"""Fixtures: the OQ-1 prototype dashboard ported to spec_version 1, plus a Parquet source."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

SALES_SPEC = """\
spec_version: 1
title: Sales Overview
subtitle: FY2026 · seeded fake data (500 orders)

sources:
  orders: { type: parquet, path: orders.parquet }

filters:
  - field: region
  - field: product_line
    label: Product line

layout:
  columns: 12

components:
  - id: kpi_revenue
    type: kpi
    title: Total revenue
    measure: { field: revenue, agg: sum }
    format: currency
    grid: { w: 4 }

  - id: kpi_orders
    type: kpi
    title: Orders
    measure: { field: order_id, agg: count }
    format: integer
    grid: { w: 4 }

  - id: kpi_aov
    type: kpi
    title: Avg order value
    measure: { field: revenue, agg: mean }
    format: currency
    grid: { w: 4 }

  - id: rev_by_region
    type: bar
    title: Revenue by region
    x: { field: region }
    y: { field: revenue, agg: sum }
    format: currency
    sort: desc
    grid: { w: 6, h: 320 }

  - id: rev_by_month
    type: line
    title: Monthly revenue by product line
    x: { field: month }
    y: { field: revenue, agg: sum }
    series: { field: product_line }
    format: currency
    grid: { w: 6, h: 320 }

  - id: rev_by_line
    type: pie
    title: Revenue share by product line
    category: { field: product_line }
    value: { field: revenue, agg: sum }
    format: currency
    grid: { w: 4, h: 320 }

  - id: orders_table
    type: table
    title: Orders
    columns:
      - { field: order_id,     label: Order }
      - { field: order_date,   label: Date }
      - { field: region,       label: Region }
      - { field: product_line, label: Product line }
      - { field: rep,          label: Rep }
      - { field: units,        label: Units,   format: integer }
      - { field: revenue,      label: Revenue, format: currency }
    sort: { field: order_date, dir: desc }
    page_size: 25
    grid: { w: 8, h: 320 }
"""


@pytest.fixture
def sales_spec() -> str:
    return SALES_SPEC


@pytest.fixture
def spec_dir(tmp_path: Path) -> Path:
    (tmp_path / "dashboard.yml").write_text(SALES_SPEC)
    pl.DataFrame(
        {
            "order_id": [1, 2],
            "order_date": ["2026-01-05", "2026-02-11"],
            "month": ["2026-01", "2026-02"],
            "region": ["West", "East"],
            "product_line": ["Hardware", "Software"],
            "rep": ["A. Okafor", "B. Lindqvist"],
            "units": [3, 1],
            "revenue": [2400.0, 450.0],
            "unused_column": ["x", "y"],
        }
    ).write_parquet(tmp_path / "orders.parquet")
    return tmp_path
