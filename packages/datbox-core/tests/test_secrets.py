import pytest
from pydantic import ValidationError

from datbox_core import secrets
from datbox_core.errors import SecretNotFound
from datbox_core.secrets import KeyringRef, SecretRef


@pytest.mark.parametrize(
    "raw",
    ["env:TOKEN", "$TOKEN", "${TOKEN}", {"env": "TOKEN"}],
)
def test_env_shorthands(raw: object) -> None:
    assert SecretRef.model_validate(raw) == SecretRef(env="TOKEN")


def test_keyring_shorthand() -> None:
    ref = SecretRef.model_validate("keyring:dat/prod/token")
    assert ref.keyring == KeyringRef(service="dat", username="prod/token")


@pytest.mark.parametrize("raw", ["TOKEN", "vault:x", {}, {"nope": 1}])
def test_invalid_refs(raw: object) -> None:
    with pytest.raises(ValidationError):
        SecretRef.model_validate(raw)


def test_describe_never_includes_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOKEN", "hunter2")
    assert "hunter2" not in SecretRef(env="TOKEN").describe()


def test_resolve_env_first(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOKEN", "from-env")
    monkeypatch.setattr(secrets, "_keyring_get", lambda s, u: "from-keyring")
    ref = SecretRef(env="TOKEN", keyring=KeyringRef(service="dat", username="x"))
    assert secrets.resolve(ref) == "from-env"


def test_resolve_falls_back_to_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TOKEN", raising=False)
    calls: list[tuple[str, str]] = []

    def fake(service: str, username: str) -> str | None:
        calls.append((service, username))
        return "from-keyring"

    monkeypatch.setattr(secrets, "_keyring_get", fake)
    ref = SecretRef(env="TOKEN", keyring=KeyringRef(service="dat", username="x"))
    assert secrets.resolve(ref) == "from-keyring"
    assert calls == [("dat", "x")]


def test_resolve_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TOKEN", raising=False)
    monkeypatch.setattr(secrets, "_keyring_get", lambda s, u: None)
    with pytest.raises(SecretNotFound, match="env:TOKEN"):
        secrets.resolve(SecretRef(env="TOKEN"))


def test_conventional_order() -> None:
    described = [r.describe() for r in secrets.conventional_refs("api-token", "prod")]
    assert described == [
        "env:DAT_PROD_API_TOKEN",
        "env:DAT_API_TOKEN",
        "keyring:dat/prod/api-token",
        "keyring:dat/api-token",
    ]


def test_lookup_by_convention(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(secrets, "_keyring_get", lambda s, u: None)
    monkeypatch.delenv("DAT_PROD_PW", raising=False)
    monkeypatch.setenv("DAT_PW", "generic")
    assert secrets.lookup("pw", "prod") == "generic"
    monkeypatch.setenv("DAT_PROD_PW", "specific")
    assert secrets.lookup("pw", "prod") == "specific"


def test_lookup_reports_everything_tried(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(secrets, "_keyring_get", lambda s, u: None)
    monkeypatch.delenv("DAT_PW", raising=False)
    with pytest.raises(SecretNotFound, match="keyring:dat/pw"):
        secrets.lookup("pw")


def test_keyring_errors_are_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    class Boom:
        @staticmethod
        def get_password(service: str, username: str) -> str:
            raise RuntimeError("no backend")

    monkeypatch.setitem(__import__("sys").modules, "keyring", Boom())
    assert secrets._keyring_get("dat", "x") is None
