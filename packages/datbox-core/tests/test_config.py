from pathlib import Path

import pytest
from pydantic import BaseModel

from datbox_core import config as cfg
from datbox_core.errors import ConfigError, SecretNotFound
from datbox_core.paths import PROFILE_ENV
from datbox_core.sources import DuckDBSource, ParquetSource


class SalesforceSettings(BaseModel):
    instance_url: str
    api_version: str = "60.0"


def test_read_profiles_file_sets_names_and_anchors_paths(user_profiles: Path) -> None:
    parsed = cfg.read_profiles_file(user_profiles)
    dev = parsed.profiles["dev"]
    assert dev.name == "dev"
    assert parsed.default == "dev"
    orders = dev.sources["orders"]
    assert isinstance(orders, ParquetSource)
    assert orders.path == (user_profiles.parent / "data" / "orders.parquet").resolve()
    prod = parsed.profiles["prod"].sources["orders"]
    assert isinstance(prod, DuckDBSource) and prod.path == Path("/abs/prod.duckdb")


def test_user_only(user_profiles: Path, project_dir: Path) -> None:
    config = cfg.load_config()
    assert config.files == [user_profiles]
    assert config.select().name == "dev"
    assert config.select("prod").name == "prod"


def test_env_var_selects_profile(
    user_profiles: Path, project_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(PROFILE_ENV, "prod")
    assert cfg.load_profile().name == "prod"
    assert cfg.load_profile("dev").name == "dev"


def test_project_file_merges_over_user(user_profiles: Path, project_dir: Path) -> None:
    (project_dir.parent / "dat.yml").write_text(
        """\
default: prod
profiles:
  dev:
    sources:
      marts: { type: duckdb, path: target/dev.duckdb, table: fct_orders }
    settings:
      salesforce: { api_version: "62.0" }
  staging:
    description: project-only
"""
    )
    config = cfg.load_config()
    assert [p.name for p in config.files] == ["profiles.yml", "dat.yml"]
    assert config.select().name == "prod"  # project default wins
    dev = config.select("dev")
    assert set(dev.sources) == {"orders", "raw", "marts"}  # section merge, not replace
    marts = dev.sources["marts"]
    assert marts.path == (project_dir.parent / "target" / "dev.duckdb").resolve()
    sf = dev.section("salesforce", SalesforceSettings)
    assert sf.instance_url == "https://dev.example.com" and sf.api_version == "62.0"
    assert dev.description == "Local dev"  # untouched by the project file
    assert config.select("staging").description == "project-only"


def test_no_files_at_all(config_dir: Path, project_dir: Path) -> None:
    config = cfg.load_config()
    assert config.files == []
    with pytest.raises(ConfigError, match="dat config init"):
        config.select()


def test_single_profile_is_implicit_default(config_dir: Path, project_dir: Path) -> None:
    (config_dir / "profiles.yml").write_text("profiles:\n  only: {}\n")
    assert cfg.load_profile().name == "only"


def test_unknown_profile_lists_available(user_profiles: Path, project_dir: Path) -> None:
    with pytest.raises(ConfigError, match="available: dev, prod"):
        cfg.load_profile("qa")


def test_invalid_yaml_and_schema(config_dir: Path, project_dir: Path) -> None:
    f = config_dir / "profiles.yml"
    f.write_text("profiles: [\n")
    with pytest.raises(ConfigError, match="invalid YAML"):
        cfg.load_config()
    f.write_text("profiles:\n  dev:\n    sorces: {}\n")
    with pytest.raises(ConfigError, match=r"profiles\.dev\.sorces"):
        cfg.load_config()
    f.write_text("- not a mapping\n")
    with pytest.raises(ConfigError, match="top level"):
        cfg.load_config()


def test_source_lookup_errors(user_profiles: Path, project_dir: Path) -> None:
    dev = cfg.load_profile("dev")
    assert isinstance(dev.source("orders"), ParquetSource)
    with pytest.raises(ConfigError, match="available: orders, raw"):
        dev.source("missing")


def test_section_validation_error_is_config_error(user_profiles: Path, project_dir: Path) -> None:
    prod = cfg.load_profile("prod")
    with pytest.raises(ConfigError, match=r"settings\.salesforce: instance_url"):
        prod.section("salesforce", SalesforceSettings)


def test_secret_declared_then_convention(
    user_profiles: Path, project_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dev = cfg.load_profile("dev")
    monkeypatch.setenv("TEST_API_TOKEN", "declared")
    assert dev.secret("api_token") == "declared"
    monkeypatch.setenv("DAT_DEV_DB_PASSWORD", "by-convention")
    assert dev.secret("db_password") == "by-convention"
    with pytest.raises(SecretNotFound):
        dev.secret("nothing")


def test_example_profiles_is_valid(tmp_path: Path) -> None:
    f = tmp_path / "profiles.yml"
    f.write_text(cfg.EXAMPLE_PROFILES)
    parsed = cfg.read_profiles_file(f)
    assert parsed.default == "dev" and "dev" in parsed.profiles
