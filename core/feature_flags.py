from __future__ import annotations

import os

CEREBRO_MODE = os.getenv("CEREBRO_MODE", "native")


def is_sandbox() -> bool:
    return CEREBRO_MODE == "sandbox"
