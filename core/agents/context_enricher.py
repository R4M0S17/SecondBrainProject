"""A8 — Proactive Context Enrichment.

Injects ambient context (upcoming events, recent files) into every query
without the agent needing to ask.
"""

from __future__ import annotations

import asyncio
from typing import Final, TypedDict

from loguru import logger

ENRICH_TIMEOUT_SEC: Final = 3


class LocaleTemplate(TypedDict):
    """Localized labels used to format ambient context."""

    events_heading: str
    files_heading: str
    no_events_markers: tuple[str, ...]


DEFAULT_LANGUAGE: Final = "en"
LOCALE_TEMPLATES: Final[dict[str, LocaleTemplate]] = {
    "en": {
        "events_heading": "UPCOMING EVENTS (next {hours}h)",
        "files_heading": "RECENT FILES",
        "no_events_markers": ("No events", "No upcoming events", "Sin eventos"),
    },
    "es": {
        "events_heading": "PRÓXIMOS EVENTOS (próximas {hours}h)",
        "files_heading": "ARCHIVOS RECIENTES",
        "no_events_markers": ("Sin eventos", "No hay eventos"),
    },
}


class ContextEnricher:
    """Enriches queries with proactive ambient context."""

    def __init__(
        self,
        authorized_read_paths: list[str],
        cerebro_files_path: str,
        enabled: bool = True,
        language: str = DEFAULT_LANGUAGE,
    ) -> None:
        self.authorized_read_paths = authorized_read_paths
        self.cerebro_files_path = cerebro_files_path
        self.enabled = enabled
        if language not in LOCALE_TEMPLATES:
            logger.warning(
                "Unsupported ContextEnricher language '{}'; using '{}'",
                language,
                DEFAULT_LANGUAGE,
            )
            language = DEFAULT_LANGUAGE
        self.language = language

    async def enrich(self, query: str) -> str:
        """Return a formatted AMBIENT_CONTEXT string for injection into system prompt.

        Calls get_upcoming_events() and search_files() in parallel with timeout.
        Returns partial results if one source fails; empty string if disabled.
        """
        if not self.enabled:
            return ""

        try:
            # Import here to avoid circular dependencies
            from core.tools.handlers.calendar import get_upcoming_events
            from core.tools.handlers.filesystem import search_files

            # Run both in parallel with timeout protection
            results = await asyncio.wait_for(
                asyncio.gather(
                    asyncio.to_thread(get_upcoming_events, hours_ahead=48),
                    asyncio.to_thread(
                        search_files,
                        "*",
                        self.authorized_read_paths,
                        base_path=self.cerebro_files_path,
                        max_results=5,
                    ),
                    return_exceptions=True,
                ),
                timeout=ENRICH_TIMEOUT_SEC,
            )

            events_str = ""
            files_str = ""
            template = LOCALE_TEMPLATES[self.language]

            # Handle results with type checking and error classification
            if isinstance(results[0], str):
                events_str = results[0]
            elif isinstance(results[0], Exception):
                logger.debug(
                    "ContextEnricher: Calendar handler failed: {}", type(results[0]).__name__
                )

            if isinstance(results[1], str):
                files_str = results[1]
            elif isinstance(results[1], Exception):
                logger.debug(
                    "ContextEnricher: Filesystem handler failed: {}", type(results[1]).__name__
                )

            # Format into ambient context section
            parts = []
            has_events = events_str and not any(
                marker in events_str for marker in template["no_events_markers"]
            )
            if has_events:
                events_heading = template["events_heading"].format(hours=48)
                parts.append(f"{events_heading}:\n{events_str}")
            if files_str:
                parts.append(f"{template['files_heading']}:\n{files_str}")

            if parts:
                return "\n\n".join(parts)
            return ""

        except TimeoutError:
            logger.warning(
                "ContextEnricher.enrich timed out after {}s (handlers exceeded timeout)",
                ENRICH_TIMEOUT_SEC,
            )
            return ""
        except Exception as e:
            logger.exception("ContextEnricher.enrich failed with unexpected error: {}", e)
            return ""
