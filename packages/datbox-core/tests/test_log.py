import logging

import pytest

from datbox_core import log


def test_logger_names_collapse_package_prefix() -> None:
    assert log.get_logger().name == "dat"
    assert log.get_logger("datbox_core.config").name == "dat.config"
    assert log.get_logger("datbox_viz.build").name == "dat.viz.build"
    assert log.get_logger("custom").name == "dat.custom"


def test_resolve_level_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(log.LOG_LEVEL_ENV, "debug")
    assert log.resolve_level() == logging.DEBUG
    assert log.resolve_level("warning") == logging.WARNING
    assert log.resolve_level(quiet=True) == logging.WARNING
    assert log.resolve_level(verbose=True) == logging.DEBUG
    monkeypatch.setenv(log.LOG_LEVEL_ENV, "nonsense")
    assert log.resolve_level() == logging.INFO


def test_configure_is_idempotent(capsys: pytest.CaptureFixture[str]) -> None:
    log.configure()
    log.configure(verbose=True)
    root = logging.getLogger("dat")
    ours = [h for h in root.handlers if type(h) is log._StderrHandler]  # pytest adds its own
    assert len(ours) == 1 and root.level == logging.DEBUG
    log.get_logger("x").debug("hello")
    assert "DEBUG   dat.x: hello" in capsys.readouterr().err
