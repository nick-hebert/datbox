"""Exception hierarchy shared by every datbox-* module."""

from __future__ import annotations


class DatError(Exception):
    """Base class for every error dat raises on purpose.

    CLI commands catch this and print the message without a traceback; anything
    else is a bug and is allowed to crash loudly.
    """


class ConfigError(DatError):
    """A config file is missing, unparsable, or fails validation."""


class SecretNotFound(DatError):
    """A secret could not be resolved from the environment or the OS keyring."""
