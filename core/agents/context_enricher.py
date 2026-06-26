"""A8 — Proactive Context Enrichment.

Injects ambient context (upcoming events, recent files) into every query
without the agent needing to ask.
"""

from __future__ import annotations

import asyncio
import os
import platform
from datetime import datetime
from typing import Final, TypedDict

from loguru import logger
from pydantic import BaseModel, field_validator

ENRICH_TIMEOUT_SEC: Final = 3


class EventsHandlerResult(BaseModel):
    """Contract for get_upcoming_events() handler return value."""

    content: str

    @field_validator("content")
    @classmethod
    def content_is_string(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("Events content must be a string")
        return v


class FilesHandlerResult(BaseModel):
    """Contract for search_files() handler return value."""

    content: str

    @field_validator("content")
    @classmethod
    def content_is_string(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("Files content must be a string")
        return v


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
        macos_permissions: dict[str, str] | None = None,
    ) -> None:
        self.authorized_read_paths = authorized_read_paths
        self.cerebro_files_path = cerebro_files_path
        self.enabled = enabled
        self.macos_permissions = macos_permissions
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

        Calendar reads use asyncio subprocess (kill on timeout). Files use to_thread.
        """
        if not self.enabled:
            return ""

        if (
            self.macos_permissions is not None
            and self.macos_permissions.get("calendar") == "denied"
        ):
            return ""

        try:
            from core.tools.handlers.calendar import format_merged_calendar_result
            from core.tools.handlers.filesystem import search_files
            from integrations.calendar_reader import BackendResult, CalendarReader

            ics_path = os.path.expanduser(os.getenv("CEREBRO_ICS", "~/.cerebro/calendar.ics"))
            reader = CalendarReader(
                ics_path=ics_path,
                use_apple_calendar=platform.system() == "Darwin",
            )

            async def _calendar_branch() -> BackendResult:
                return await reader.get_upcoming_events_async(48, apple_communicate_timeout=3.0)

            results = await asyncio.wait_for(
                asyncio.gather(
                    _calendar_branch(),
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

            cal_raw = results[0]
            files_raw = results[1]

            events_str = ""
            files_str = ""
            template = LOCALE_TEMPLATES[self.language]
            if self.language == "es":
                now_str = datetime.now().astimezone().strftime("%A %d de %B de %Y, %H:%M %Z")
            else:
                now_str = datetime.now().astimezone().strftime("%A %B %d, %Y %H:%M %Z")

            if isinstance(cal_raw, Exception):
                logger.debug("ContextEnricher: Calendar async failed: {}", type(cal_raw).__name__)
            elif isinstance(cal_raw, BackendResult):
                if cal_raw.status in ("permission_denied", "timeout", "error", "no_calendar") and (
                    not cal_raw.events
                ):
                    events_str = ""
                elif cal_raw.events:
                    events_str = format_merged_calendar_result(cal_raw, 48, now_str)
                else:
                    events_str = ""
            else:
                logger.debug(
                    "ContextEnricher: unexpected calendar result type: {}",
                    type(cal_raw).__name__,
                )

            if isinstance(files_raw, Exception):
                logger.debug(
                    "ContextEnricher: Filesystem handler failed: {}", type(files_raw).__name__
                )
            elif isinstance(files_raw, str):
                try:
                    validated = FilesHandlerResult(content=files_raw)
                    files_str = validated.content
                except Exception as e:
                    logger.debug("ContextEnricher: Files result validation failed: {}", e)
            else:
                logger.debug(
                    "ContextEnricher: Filesystem handler returned unexpected type: {}",
                    type(files_raw).__name__,
                )

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
