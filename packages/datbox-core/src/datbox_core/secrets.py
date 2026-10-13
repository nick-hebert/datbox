"""Secrets resolution: environment variables first, OS keyring as the fallback.

Secrets never live in config files or the repo (brief, principle 5). A profile
names a secret; this module finds its value at run time.

Two ways to name a secret:

* **Explicit reference** in ``profiles.yml``::

      secrets:
        api_token: { env: SF_API_TOKEN }
        password:  { keyring: { service: dat, username: prod/password } }
        both:      { env: SF_PW, keyring: { service: dat, username: sf } }

  String shorthands are accepted: ``"env:SF_API_TOKEN"``, ``"$SF_API_TOKEN"``,
  ``"${SF_API_TOKEN}"``, ``"keyring:service/username"``.

* **Convention** (nothing declared): ``profile.secret("api_token")`` on profile
  ``prod`` looks up, in order, the environment variables ``DAT_PROD_API_TOKEN``
  and ``DAT_API_TOKEN``, then keyring entries ``(service="dat",
  username="prod/api_token")`` and ``(service="dat", username="api_token")``.

The ``keyring`` package is optional (``pip install datbox-core[keyring]``).
Without it, keyring lookups are skipped and only the environment is consulted.
"""

from __future__ import annotations

import os
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from datbox_core.errors import SecretNotFound

DEFAULT_KEYRING_SERVICE = "dat"
ENV_PREFIX = "DAT"

_ENV_SHORTHAND = re.compile(r"^(?:env:|\$\{?)([A-Za-z_][A-Za-z0-9_]*)\}?$")
_KEYRING_SHORTHAND = re.compile(r"^keyring:([^/]+)/(.+)$")


class KeyringRef(BaseModel):
    """A ``(service, username)`` pair as stored by the OS keyring."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    service: str
    username: str


class SecretRef(BaseModel):
    """Where to find one secret. At least one of ``env`` / ``keyring`` is required."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    env: str | None = None
    keyring: KeyringRef | None = None

    @model_validator(mode="before")
    @classmethod
    def _parse_shorthand(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        if m := _ENV_SHORTHAND.match(value):
            return {"env": m.group(1)}
        if m := _KEYRING_SHORTHAND.match(value):
            return {"keyring": {"service": m.group(1), "username": m.group(2)}}
        raise ValueError(
            f"unrecognised secret reference {value!r}; use 'env:NAME', '$NAME', "
            "'keyring:service/username', or a mapping with 'env' and/or 'keyring'"
        )

    @model_validator(mode="after")
    def _at_least_one(self) -> SecretRef:
        if self.env is None and self.keyring is None:
            raise ValueError("a secret reference needs 'env' and/or 'keyring'")
        return self

    def describe(self) -> str:
        """Human-readable location of the secret — never its value."""
        parts: list[str] = []
        if self.env:
            parts.append(f"env:{self.env}")
        if self.keyring:
            parts.append(f"keyring:{self.keyring.service}/{self.keyring.username}")
        return " → ".join(parts)


def resolve(ref: SecretRef) -> str:
    """Resolve an explicit reference: environment first, then keyring."""
    if ref.env is not None:
        value = os.environ.get(ref.env)
        if value:
            return value
    if ref.keyring is not None:
        value = _keyring_get(ref.keyring.service, ref.keyring.username)
        if value:
            return value
    raise SecretNotFound(f"secret not found at {ref.describe()}")


def lookup(name: str, profile: str | None = None) -> str:
    """Resolve a secret by convention (see module docstring)."""
    candidates = conventional_refs(name, profile)
    for ref in candidates:
        try:
            return resolve(ref)
        except SecretNotFound:
            continue
    tried = ", ".join(ref.describe() for ref in candidates)
    raise SecretNotFound(f"secret {name!r} not found; tried {tried}")


def conventional_refs(name: str, profile: str | None = None) -> list[SecretRef]:
    """The references ``lookup`` tries, in order. Exposed so CLIs can print them."""
    slug = _env_slug(name)
    refs: list[SecretRef] = []
    if profile:
        refs.append(SecretRef(env=f"{ENV_PREFIX}_{_env_slug(profile)}_{slug}"))
    refs.append(SecretRef(env=f"{ENV_PREFIX}_{slug}"))
    if profile:
        refs.append(
            SecretRef(
                keyring=KeyringRef(service=DEFAULT_KEYRING_SERVICE, username=f"{profile}/{name}")
            )
        )
    refs.append(SecretRef(keyring=KeyringRef(service=DEFAULT_KEYRING_SERVICE, username=name)))
    return refs


def keyring_available() -> bool:
    """True when the optional ``keyring`` package can be imported."""
    try:
        import keyring  # noqa: F401
    except ImportError:
        return False
    return True


def _keyring_get(service: str, username: str) -> str | None:
    """Read from the OS keyring; ``None`` when unavailable or missing."""
    try:
        import keyring
    except ImportError:
        return None
    try:
        return keyring.get_password(service, username)
    except Exception:  # keyring backends raise a zoo of errors; all mean "not here"
        return None


def _env_slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").upper()
