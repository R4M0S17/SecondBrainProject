"""A8 — Proactive Context Enrichment.

Injects ambient context (upcoming events, recent files) into every query
without the agent needing to ask.
"""

from __future__ import annotations

import asyncio
from loguru import logger


class ContextEnricher:
    """Enriches queries with proactive ambient context."""

    def __init__(
        self,
        authorized_read_paths: list[str],
        cerebro_files_path: str,
        enabled: bool = True,
    ) -> None:
        self.authorized_read_paths = authorized_read_paths
        self.cerebro_files_path = cerebro_files_path
        self.enabled = enabled

    async def enrich(self, query: str) -> str:
        """Return a formatted AMBIENT_CONTEXT string for injection into system prompt.

        Calls get_upcoming_events() and search_files() in parallel. Returns empty
        string if disabled or both queries return nothing.
        """
        if not self.enabled:
            return ""

        try:
            # Import here to avoid circular dependencies
            from core.tools.handlers.calendar import get_upcoming_events
            from core.tools.handlers.filesystem import search_files

            # Run both in parallel using asyncio.to_thread
            results = await asyncio.gather(
                asyncio.to_thread(get_upcoming_events, hours_ahead=48),
                asyncio.to_thread(
                    search_files,
                    "*",
                    self.authorized_read_paths,
                    base_path=self.cerebro_files_path,
                    max_results=5,
                ),
                return_exceptions=True,
            )

            events_str = results[0] if isinstance(results[0], str) else ""
            files_str = results[1] if isinstance(results[1], str) else ""

            # Format into ambient context section
            parts = []
            if events_str and "Sin eventos" not in events_str:
                parts.append(f"PRÓXIMOS EVENTOS (próximas 48h):\n{events_str}")
            if files_str:
                parts.append(f"ARCHIVOS RECIENTES:\n{files_str}")

            if parts:
                return "\n\n".join(parts)
            return ""

        except Exception as e:
            logger.exception("ContextEnricher.enrich failed: {}", e)
            return ""
