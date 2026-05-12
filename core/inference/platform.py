from __future__ import annotations

import platform
import sys


def is_apple_silicon() -> bool:
    return sys.platform == "darwin" and platform.machine() == "arm64"


def mlx_available() -> bool:
    if not is_apple_silicon():
        return False
    try:
        import mlx.core  # noqa: F401
        import mlx_lm  # noqa: F401

        return True
    except ImportError:
        return False
