"""Module 10 — Proactive Scheduler.

Runs background checks every 5 minutes via APScheduler and fires contextual
notifications when trigger conditions are met:

  1. calendar_reminder  — upcoming calendar event ≤ 1h away (requires Module 11)
  2. file_checkpoint    — a single file modified ≥ 5 times in the current day
  3. resume_context     — 2h of inactivity detected during work hours (9–18)
  4. new_document       — a freshly indexed document is now queryable

All triggers are silenced when `do_not_disturb` is True in the settings dict
returned by `settings_getter`.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from apscheduler.schedulers.background import BackgroundScheduler
from loguru import logger

# ──────────────────────────────────────────────────────────────────────────────
# Domain types
# ──────────────────────────────────────────────────────────────────────────────


class TriggerKind(StrEnum):
    CALENDAR_REMINDER = "calendar_reminder"
    FILE_CHECKPOINT = "file_checkpoint"
    RESUME_CONTEXT = "resume_context"
    NEW_DOCUMENT = "new_document"


@dataclass
class TriggerEvent:
    kind: TriggerKind
    message: str
    payload: dict = field(default_factory=dict)


class NotificationSink(Protocol):
    def notify(self, event: TriggerEvent) -> None: ...


# ──────────────────────────────────────────────────────────────────────────────
# Scheduler
# ──────────────────────────────────────────────────────────────────────────────

_WORK_HOUR_START = 9
_WORK_HOUR_END = 18
_INACTIVITY_THRESHOLD_SECONDS = 2 * 3600  # 2 hours
_FILE_MOD_THRESHOLD = 5  # modifications per day
_CALENDAR_LOOKAHEAD_SECONDS = 3600  # 1 hour


class ProactiveScheduler:
    """APScheduler-backed scheduler that checks triggers every 5 minutes."""

    def __init__(
        self,
        sink: NotificationSink,
        settings_getter: Callable[[], dict],
        *,
        interval_seconds: int = 300,
    ) -> None:
        self._sink = sink
        self._settings_getter = settings_getter
        self._interval_seconds = interval_seconds

        self._last_activity: datetime = datetime.now(UTC)
        # path → list of modification timestamps (today only)
        self._file_mods: dict[str, list[datetime]] = defaultdict(list)
        # calendar event source (optional — injected after Module 11 is active)
        self._calendar_reader: object | None = None

        self._scheduler = BackgroundScheduler()
        self._scheduler.add_job(
            self._tick,
            trigger="interval",
            seconds=self._interval_seconds,
            id="proactive_tick",
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("ProactiveScheduler started (interval={}s)", self._interval_seconds)

    def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("ProactiveScheduler stopped")

    # ------------------------------------------------------------------
    # External event hooks (called by other subsystems)
    # ------------------------------------------------------------------

    def record_activity(self) -> None:
        """Call this on every user query to reset the inactivity clock."""
        self._last_activity = datetime.now(UTC)

    def record_file_modification(self, path: str) -> None:
        """Call this when the file watcher detects a write event."""
        now = datetime.now(UTC)
        today = now.date()
        # prune timestamps from previous days
        self._file_mods[path] = [ts for ts in self._file_mods[path] if ts.date() == today]
        self._file_mods[path].append(now)
        events = self.check_file_activity({path: len(self._file_mods[path])})
        self._emit_all(events)

    def on_document_indexed(self, path: str) -> TriggerEvent | None:
        """Call this when a new document finishes indexing."""
        event = TriggerEvent(
            kind=TriggerKind.NEW_DOCUMENT,
            message=f"New document ready for query: {path}",
            payload={"path": path},
        )
        self._emit_all([event])
        return event

    def attach_calendar_reader(self, reader: object) -> None:
        """Inject a Module 11 CalendarReader after it becomes available."""
        self._calendar_reader = reader

    # ------------------------------------------------------------------
    # Trigger logic (pure — easy to unit-test)
    # ------------------------------------------------------------------

    def check_file_activity(self, modifications: dict[str, int]) -> list[TriggerEvent]:
        """Return checkpoint events for files that crossed the daily threshold."""
        events: list[TriggerEvent] = []
        for path, count in modifications.items():
            if count >= _FILE_MOD_THRESHOLD:
                events.append(
                    TriggerEvent(
                        kind=TriggerKind.FILE_CHECKPOINT,
                        message=(
                            f"'{path}' has been modified {count} times today. "
                            "Consider saving a summary or checkpoint."
                        ),
                        payload={"path": path, "modification_count": count},
                    )
                )
        return events

    def check_inactivity(self, last_activity: datetime) -> list[TriggerEvent]:
        """Return a resume event if inactivity threshold is crossed during work hours."""
        now = datetime.now(UTC)
        local_hour = now.hour  # UTC — callers should pass tz-aware datetimes
        if not (_WORK_HOUR_START <= local_hour < _WORK_HOUR_END):
            return []
        elapsed = (now - last_activity).total_seconds()
        if elapsed >= _INACTIVITY_THRESHOLD_SECONDS:
            return [
                TriggerEvent(
                    kind=TriggerKind.RESUME_CONTEXT,
                    message="You've been inactive for 2+ hours. Resume your last work context?",
                    payload={"inactive_seconds": int(elapsed)},
                )
            ]
        return []

    def check_calendar(self) -> list[TriggerEvent]:
        """Return reminder events for calendar events starting within 1 hour."""
        if self._calendar_reader is None:
            return []
        events: list[TriggerEvent] = []
        try:
            upcoming = self._calendar_reader.get_upcoming_events(hours_ahead=1)  # type: ignore[union-attr]
            now = datetime.now(UTC)
            for ev in upcoming:
                start = ev.start
                if not start.tzinfo:
                    start = start.replace(tzinfo=UTC)
                seconds_away = (start - now).total_seconds()
                if 0 <= seconds_away <= _CALENDAR_LOOKAHEAD_SECONDS:
                    events.append(
                        TriggerEvent(
                            kind=TriggerKind.CALENDAR_REMINDER,
                            message=f"Upcoming event in {int(seconds_away // 60)}m: {ev.title}",
                            payload={
                                "title": ev.title,
                                "start": start.isoformat(),
                                "seconds_away": int(seconds_away),
                            },
                        )
                    )
        except Exception as exc:
            logger.warning("Calendar check failed: {}", exc)
        return events

    # ------------------------------------------------------------------
    # Internal tick (runs every interval)
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        if self._is_dnd():
            return

        events: list[TriggerEvent] = []
        events.extend(self.check_inactivity(self._last_activity))
        events.extend(self.check_calendar())
        self._emit_all(events)

    def _emit_all(self, events: list[TriggerEvent]) -> None:
        if self._is_dnd():
            return
        for ev in events:
            try:
                self._sink.notify(ev)
            except Exception as exc:
                logger.warning("Notification sink error: {}", exc)

    def _is_dnd(self) -> bool:
        try:
            return bool(self._settings_getter().get("do_not_disturb", False))
        except Exception:
            return False
