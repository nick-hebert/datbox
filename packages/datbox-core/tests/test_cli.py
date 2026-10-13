from pathlib import Path

import pytest
from typer.testing import CliRunner

from datbox_core import __version__
from datbox_core.cli import build_app
from datbox_core.errors import DatError

runner = CliRunner()


def test_help_runs() -> None:
    result = runner.invoke(build_app(), ["--help"])
    assert result.exit_code == 0
    assert "Data Analyst Toolbox" in result.output


def test_version_flag() -> None:
    result = runner.invoke(build_app(), ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_plugins_command_with_none_installed() -> None:
    result = runner.invoke(build_app(), ["plugins"])
    assert result.exit_code == 0
    assert "No plugins installed" in result.output


def test_config_paths(config_dir: Path, project_dir: Path) -> None:
    result = runner.invoke(build_app(), ["config", "paths"])
    assert result.exit_code == 0
    assert str(config_dir / "profiles.yml") in result.output
    assert "[missing]" in result.output


def test_config_init_then_show(
    config_dir: Path, project_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TEST_SECRET", "s3cret")
    assert runner.invoke(build_app(), ["config", "init"]).exit_code == 0
    assert (config_dir / "profiles.yml").is_file()
    again = runner.invoke(build_app(), ["config", "init"])
    assert isinstance(again.exception, DatError)

    show = runner.invoke(build_app(), ["config", "show"])
    assert show.exit_code == 0, show.output
    assert "profile: dev" in show.output
    assert "env:DAT_DEV_NAME" in show.output  # convention is explained when nothing is declared

    as_json = runner.invoke(build_app(), ["config", "show", "--json"])
    assert as_json.exit_code == 0 and '"name": "dev"' in as_json.output


def test_config_show_redacts_secret_values(
    user_profiles: Path, project_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TEST_API_TOKEN", "hunter2")
    show = runner.invoke(build_app(), ["config", "show", "--profile", "dev"])
    assert show.exit_code == 0, show.output
    assert "env:TEST_API_TOKEN" in show.output
    assert "hunter2" not in show.output
    assert "orders" in show.output and "parquet" in show.output


def test_config_show_unknown_profile_is_dat_error(user_profiles: Path, project_dir: Path) -> None:
    result = runner.invoke(build_app(), ["config", "show", "--profile", "qa"])
    assert isinstance(result.exception, DatError)
