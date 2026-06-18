"""Adaptive context length based on available RAM."""

from __future__ import annotations

import os
import re
from pathlib import Path


class AdaptiveContext:
    """Select context window size based on RAM pressure and query complexity.

    A 4096-token KV cache at Q4_K costs ~400 MB.
    A 2048-token KV cache costs ~200 MB.
    """

    def __init__(self) -> None:
        self._current_ctx = 4096
        self._enabled = os.getenv("CEREBRO_ADAPTIVE_CTX_ENABLED", "true").lower() == "true"

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def current(self) -> int:
        return self._current_ctx

    def select(self, query: str, available_ram_gb: float) -> int:
        if not self._enabled:
            return 4096
        if available_ram_gb < 1.0:
            return 2048 if len(query) < 200 else 4096
        if available_ram_gb < 2.0:
            return 3072
        return 4096

    def update_args(self, args_path: Path, new_ctx: int) -> bool:
        """Rewrite --ctx-size in the args file and return True if changed."""
        if not args_path.is_file() or new_ctx == self._current_ctx:
            return False
        content = args_path.read_text()
        updated = re.sub(r"--ctx-size \d+", f"--ctx-size {new_ctx}", content)
        if updated == content:
            updated = content.rstrip() + f"\n--ctx-size {new_ctx}\n"
        args_path.write_text(updated)
        self._current_ctx = new_ctx
        return True
