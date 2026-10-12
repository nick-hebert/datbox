from importlib.metadata import EntryPoint

import typer

from datbox_core import plugins


def test_discover_loads_valid_typer_app(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    fake_app = typer.Typer()

    class FakeEP(EntryPoint):
        def load(self):  # type: ignore[override]
            return fake_app

    ep = FakeEP(name="fake", value="x:y", group=plugins.PLUGIN_GROUP)
    monkeypatch.setattr(plugins, "_iter_entry_points", lambda: [ep])
    loaded, failed = plugins.discover()
    assert [p.name for p in loaded] == ["fake"]
    assert loaded[0].app is fake_app
    assert failed == []


def test_discover_reports_broken_plugin(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    class BrokenEP(EntryPoint):
        def load(self):  # type: ignore[override]
            raise ImportError("boom")

    ep = BrokenEP(name="broken", value="x:y", group=plugins.PLUGIN_GROUP)
    monkeypatch.setattr(plugins, "_iter_entry_points", lambda: [ep])
    loaded, failed = plugins.discover()
    assert loaded == []
    assert failed[0].name == "broken"
    assert "ImportError" in failed[0].error
