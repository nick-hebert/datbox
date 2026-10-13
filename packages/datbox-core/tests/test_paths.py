from pathlib import Path

import pytest

from datbox_core import paths


def test_config_dir_prefers_dat_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(paths.CONFIG_DIR_ENV, str(tmp_path / "custom"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert paths.config_dir() == tmp_path / "custom"


def test_config_dir_uses_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv(paths.CONFIG_DIR_ENV, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert paths.user_profiles_path() == tmp_path / "xdg" / "dat" / "profiles.yml"


def test_config_dir_defaults_to_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(paths.CONFIG_DIR_ENV, raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    assert paths.config_dir() == Path.home() / ".config" / "dat"


def test_find_project_file_walks_up(tmp_path: Path) -> None:
    (tmp_path / "dat.yml").write_text("profiles: {}\n")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert paths.find_project_file(nested) == tmp_path / "dat.yml"


def test_find_project_file_none(tmp_path: Path) -> None:
    assert paths.find_project_file(tmp_path) is None


def test_expand_handles_tilde_and_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAT_TEST_DIR", "/srv/data")
    assert paths.expand("$DAT_TEST_DIR/x.parquet") == Path("/srv/data/x.parquet")
    assert paths.expand("~/x") == Path.home() / "x"
