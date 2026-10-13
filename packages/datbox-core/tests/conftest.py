"""Shared fixtures: an isolated config dir, a clean environment, and a sample frame."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import polars as pl
import pytest

from datbox_core import secrets
from datbox_core.paths import CONFIG_DIR_ENV, PROFILE_ENV

PROFILES_YAML = """\
default: dev
profiles:
  dev:
    description: Local dev
    sources:
      orders: { type: parquet, path: data/orders.parquet }
      raw:    { type: csv, path: data/raw.csv, delimiter: ";" }
    secrets:
      api_token: { env: TEST_API_TOKEN }
    settings:
      salesforce: { instance_url: https://dev.example.com, api_version: "61.0" }
  prod:
    sources:
      orders: { type: duckdb, path: /abs/prod.duckdb, table: fct_orders }
"""


@pytest.fixture
def frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "order_id": [1, 2, 3],
            "region": ["West", "East", "West"],
            "revenue": [100.0, 250.5, 75.25],
        }
    )


@pytest.fixture
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty user config dir, with every dat env var cleared and keyring stubbed empty."""
    cfg = tmp_path / "config"
    cfg.mkdir()
    monkeypatch.setenv(CONFIG_DIR_ENV, str(cfg))
    monkeypatch.delenv(PROFILE_ENV, raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(secrets, "_keyring_get", lambda service, username: None)
    return cfg


@pytest.fixture
def user_profiles(config_dir: Path) -> Path:
    path = config_dir / "profiles.yml"
    path.write_text(PROFILES_YAML)
    return path


@pytest.fixture
def project_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A project directory with no dat.yml yet; cwd is moved into it."""
    proj = tmp_path / "proj" / "sub"
    proj.mkdir(parents=True)
    monkeypatch.chdir(proj)
    yield proj
