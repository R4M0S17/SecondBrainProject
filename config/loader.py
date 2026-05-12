"""Module 12 — Config Loader.

Loads settings from a TOML file and exposes them as a plain dict.
ConfigError is raised for any loading failure so callers get a single,
structured exception type to catch.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

_DEFAULT_SETTINGS = Path(__file__).parent / "settings.toml"


class ConfigError(Exception):
    """Raised when the settings file is missing, unreadable, or contains invalid TOML."""


def load_settings(path: str | None = None) -> dict:
    """Load and return the TOML settings as a plain dict.

    Args:
        path: Absolute or relative path to a .toml file.  Defaults to the
              bundled ``config/settings.toml`` when omitted.

    Raises:
        ConfigError: If the file does not exist or contains invalid TOML.
    """
    p = Path(path) if path is not None else _DEFAULT_SETTINGS
    if not p.exists():
        raise ConfigError(f"Settings file not found: {p}")
    try:
        return tomllib.loads(p.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML in {p}: {exc}") from exc
