from typer.testing import CliRunner

from datbox_core import __version__
from datbox_core.cli import build_app

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
