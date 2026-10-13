"""Profiles: the one place a dat user points a tool at a new company, org, or warehouse.

``profiles.yml`` (user) and ``dat.yml`` (project) share one schema::

    default: dev                      # profile used when none is named
    profiles:
      dev:
        description: local dbt build
        sources:                      # named tables any module can read
          marts: { type: duckdb, path: ~/dbt/target/dev.duckdb, table: fct_orders }
        secrets:                      # optional explicit secret locations
          api_token: { env: SF_API_TOKEN }
        settings:                     # per-module blocks, validated by that module
          salesforce: { instance_url: https://example.my.salesforce.com }
      prod:
        ...

Profile selection order: explicit name → ``$DAT_PROFILE`` → project ``default`` →
user ``default`` → a profile literally named ``default`` → the only profile if
there is exactly one. Project profiles are merged *section by section* over user
profiles of the same name (a project can add a source to ``dev`` without
repeating the whole profile).

Modules never read YAML themselves. They call :func:`load_profile` and then
``profile.section("salesforce", SalesforceSettings)`` to get their own typed
settings, ``profile.source("marts")`` for a table, ``profile.secret("api_token")``
for a credential.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from datbox_core import secrets as _secrets
from datbox_core.errors import ConfigError
from datbox_core.paths import PROFILE_ENV, find_project_file, user_profiles_path
from datbox_core.sources import Source

M = TypeVar("M", bound=BaseModel)

_NAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]*$"


class Profile(BaseModel):
    """One environment: a named bundle of sources, secret locations, and module settings."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(default="", pattern=_NAME_PATTERN, description="Set by the loader.")
    description: str | None = None
    sources: dict[str, Source] = Field(default_factory=dict)
    secrets: dict[str, _secrets.SecretRef] = Field(default_factory=dict)
    settings: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @field_validator("sources", "secrets", "settings", mode="before")
    @classmethod
    def _empty_block_is_empty_dict(cls, value: Any) -> Any:
        """``sources:`` with nothing under it parses as ``None`` in YAML; treat it as ``{}``."""
        return {} if value is None else value

    def source(self, name: str) -> Source:
        """The named source, or a ``ConfigError`` listing what exists."""
        try:
            return self.sources[name]
        except KeyError:
            raise ConfigError(
                f"profile {self.name!r} has no source {name!r}; available: {_listing(self.sources)}"
            ) from None

    def secret(self, name: str) -> str:
        """Resolve a secret: declared reference if any, else the naming convention."""
        ref = self.secrets.get(name)
        if ref is not None:
            return _secrets.resolve(ref)
        return _secrets.lookup(name, self.name or None)

    def section(self, key: str, model: type[M]) -> M:
        """Validate this profile's ``settings[key]`` block with a module's own model."""
        raw = self.settings.get(key, {})
        try:
            return model.model_validate(raw)
        except ValidationError as exc:
            raise ConfigError(
                f"profile {self.name!r}, settings.{key}: {_format_validation(exc)}"
            ) from None

    def merged_over(self, base: Profile) -> Profile:
        """This profile's sections laid over ``base`` (project over user)."""
        return Profile(
            name=self.name or base.name,
            description=self.description or base.description,
            sources={**base.sources, **self.sources},
            secrets={**base.secrets, **self.secrets},
            settings={
                key: {**base.settings.get(key, {}), **self.settings.get(key, {})}
                for key in base.settings.keys() | self.settings.keys()
            },
        )


class ProfilesFile(BaseModel):
    """The parsed content of one ``profiles.yml`` / ``dat.yml``."""

    model_config = ConfigDict(extra="forbid")

    default: str | None = Field(default=None, pattern=_NAME_PATTERN)
    profiles: dict[str, Profile] = Field(default_factory=dict)
    path: Path | None = Field(default=None, exclude=True, description="Set by the loader.")


class Config(BaseModel):
    """Everything dat found on disk, already merged."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    user: ProfilesFile | None = None
    project: ProfilesFile | None = None
    profiles: dict[str, Profile] = Field(default_factory=dict)

    @property
    def files(self) -> list[Path]:
        return [f.path for f in (self.user, self.project) if f is not None and f.path]

    def select(self, name: str | None = None) -> Profile:
        """Pick a profile by the selection order in the module docstring."""
        candidates = [
            name,
            os.environ.get(PROFILE_ENV) or None,
            self.project.default if self.project else None,
            self.user.default if self.user else None,
            "default" if "default" in self.profiles else None,
            next(iter(self.profiles)) if len(self.profiles) == 1 else None,
        ]
        chosen = next((c for c in candidates if c), None)
        if chosen is None:
            if not self.profiles:
                raise ConfigError(
                    "no profiles found; run 'dat config init' to create "
                    f"{user_profiles_path()} or add a dat.yml to the project"
                )
            raise ConfigError(
                f"no profile selected; use --profile, set ${PROFILE_ENV}, or add "
                f"'default:' to a config file. Available: {_listing(self.profiles)}"
            )
        try:
            return self.profiles[chosen]
        except KeyError:
            raise ConfigError(
                f"profile {chosen!r} not found; available: {_listing(self.profiles)}"
            ) from None


def read_profiles_file(path: Path) -> ProfilesFile:
    """Parse and validate one YAML file. Relative source paths anchor at the file's directory."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot read {path}: {exc.strerror}") from None
    try:
        raw = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: invalid YAML: {exc}") from None
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: top level must be a mapping with 'profiles:'")
    try:
        parsed = ProfilesFile.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"{path}: {_format_validation(exc)}") from None
    base = path.resolve().parent
    for pname, profile in parsed.profiles.items():
        profile.name = pname
        profile.sources = {k: s.with_base(base) for k, s in profile.sources.items()}
    parsed.path = path
    return parsed


def load_config(
    *,
    user_file: Path | None = None,
    project_dir: Path | None = None,
    project_file: Path | None = None,
) -> Config:
    """Read the user and project files (either may be absent) and merge them."""
    upath = user_file if user_file is not None else user_profiles_path()
    ppath = project_file if project_file is not None else find_project_file(project_dir)
    user = read_profiles_file(upath) if upath.is_file() else None
    project = read_profiles_file(ppath) if ppath is not None and ppath.is_file() else None

    merged: dict[str, Profile] = dict(user.profiles) if user else {}
    if project:
        for pname, prof in project.profiles.items():
            merged[pname] = prof.merged_over(merged[pname]) if pname in merged else prof
    return Config(user=user, project=project, profiles=merged)


def load_profile(name: str | None = None, **kwargs: Any) -> Profile:
    """One-call convenience for modules: ``load_config(**kwargs).select(name)``."""
    return load_config(**kwargs).select(name)


EXAMPLE_PROFILES = """\
# dat profiles — one entry per environment. Secrets never go in this file:
# reference them (env: / keyring:) or rely on the DAT_<PROFILE>_<NAME> convention.
default: dev

profiles:
  dev:
    description: Local development
    sources:
      # marts: { type: duckdb, path: ~/projects/my-dbt/target/dev.duckdb, table: fct_orders }
      # orders: { type: parquet, path: ~/data/orders.parquet }
    secrets:
      # api_token: { env: SF_API_TOKEN }
    settings: {}
"""


def _listing(d: dict[str, Any]) -> str:
    return ", ".join(sorted(d)) or "(none)"


def _format_validation(exc: ValidationError) -> str:
    lines = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "<root>"
        lines.append(f"{loc}: {err['msg']}")
    return "; ".join(lines)
