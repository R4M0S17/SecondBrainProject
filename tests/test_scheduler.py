"""Tests for Module 10 — Proactive Scheduler."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from scheduler.proactive import ProactiveScheduler, TriggerEvent, TriggerKind

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _make_scheduler(dnd: bool = False) -> tuple[ProactiveScheduler, MagicMock]:
    sink = MagicMock()
    scheduler = ProactiveScheduler(
        sink=sink,
        settings_getter=lambda: {"do_not_disturb": dnd},
        interval_seconds=300,
    )
    return scheduler, sink


# ──────────────────────────────────────────────────────────────────────────────
# Lifecycle
# ──────────────────────────────────────────────────────────────────────────────


def test_scheduler_starts_and_stops():
    sched, _ = _make_scheduler()
    sched.start()
    assert sched._scheduler.running
    sched.stop()
    assert not sched._scheduler.running


def test_scheduler_stop_is_idempotent():
    sched, _ = _make_scheduler()
    sched.stop()  # stop before start — should not raise
    sched.start()
    sched.stop()
    sched.stop()  # double-stop — should not raise


# ──────────────────────────────────────────────────────────────────────────────
# Trigger: file_checkpoint
# ──────────────────────────────────────────────────────────────────────────────


def test_file_checkpoint_fires_at_threshold():
    sched, _ = _make_scheduler()
    events = sched.check_file_activity({"/notes/todo.md": 5})
    assert len(events) == 1
    assert events[0].kind == TriggerKind.FILE_CHECKPOINT


def test_file_checkpoint_does_not_fire_below_threshold():
    sched, _ = _make_scheduler()
    events = sched.check_file_activity({"/notes/todo.md": 4})
    assert events == []


def test_file_checkpoint_fires_above_threshold():
    sched, _ = _make_scheduler()
    events = sched.check_file_activity({"/notes/todo.md": 10})
    assert len(events) == 1


def test_file_checkpoint_payload_contains_path_and_count():
    sched, _ = _make_scheduler()
    events = sched.check_file_activity({"/doc.py": 7})
    assert events[0].payload["path"] == "/doc.py"
    assert events[0].payload["modification_count"] == 7


def test_file_checkpoint_multiple_files():
    sched, _ = _make_scheduler()
    events = sched.check_file_activity({"/a.md": 6, "/b.md": 2, "/c.md": 5})
    kinds = {e.payload["path"] for e in events}
    assert "/a.md" in kinds
    assert "/c.md" in kinds
    assert "/b.md" not in kinds


def test_record_file_modification_notifies_sink_at_threshold():
    sched, sink = _make_scheduler()
    for _ in range(5):
        sched.record_file_modification("/notes/daily.md")
    assert sink.notify.called
    last_event: TriggerEvent = sink.notify.call_args[0][0]
    assert last_event.kind == TriggerKind.FILE_CHECKPOINT


# ──────────────────────────────────────────────────────────────────────────────
# Trigger: resume_context (inactivity)
# ──────────────────────────────────────────────────────────────────────────────


def test_inactivity_fires_after_2h_during_work_hours():
    sched, _ = _make_scheduler()
    # freeze "now" at 14:00 UTC (work hours)
    fake_now = datetime(2026, 5, 6, 14, 0, 0, tzinfo=UTC)
    last_activity = fake_now - timedelta(hours=3)
    with patch("scheduler.proactive.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        events = sched.check_inactivity(last_activity)
    assert len(events) == 1
    assert events[0].kind == TriggerKind.RESUME_CONTEXT


def test_inactivity_does_not_fire_within_2h():
    sched, _ = _make_scheduler()
    fake_now = datetime(2026, 5, 6, 14, 0, 0, tzinfo=UTC)
    last_activity = fake_now - timedelta(hours=1)
    with patch("scheduler.proactive.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        events = sched.check_inactivity(last_activity)
    assert events == []


def test_inactivity_silent_outside_work_hours():
    sched, _ = _make_scheduler()
    # 22:00 UTC — outside work hours
    fake_now = datetime(2026, 5, 6, 22, 0, 0, tzinfo=UTC)
    last_activity = fake_now - timedelta(hours=5)
    with patch("scheduler.proactive.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        events = sched.check_inactivity(last_activity)
    assert events == []


def test_inactivity_payload_contains_elapsed_seconds():
    sched, _ = _make_scheduler()
    fake_now = datetime(2026, 5, 6, 14, 0, 0, tzinfo=UTC)
    last_activity = fake_now - timedelta(hours=2, minutes=30)
    with patch("scheduler.proactive.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        events = sched.check_inactivity(last_activity)
    assert events[0].payload["inactive_seconds"] >= 7200


# ──────────────────────────────────────────────────────────────────────────────
# Trigger: new_document
# ──────────────────────────────────────────────────────────────────────────────


def test_on_document_indexed_returns_event():
    sched, sink = _make_scheduler()
    event = sched.on_document_indexed("/docs/paper.pdf")
    assert event is not None
    assert event.kind == TriggerKind.NEW_DOCUMENT
    assert "/docs/paper.pdf" in event.message


def test_on_document_indexed_notifies_sink():
    sched, sink = _make_scheduler()
    sched.on_document_indexed("/docs/paper.pdf")
    sink.notify.assert_called_once()
    fired: TriggerEvent = sink.notify.call_args[0][0]
    assert fired.kind == TriggerKind.NEW_DOCUMENT


# ──────────────────────────────────────────────────────────────────────────────
# Trigger: calendar_reminder
# ──────────────────────────────────────────────────────────────────────────────


def _mock_calendar_event(title: str, start: datetime) -> MagicMock:
    ev = MagicMock()
    ev.title = title
    ev.start = start
    return ev


def test_calendar_reminder_fires_within_1h():
    sched, _ = _make_scheduler()
    fake_now = datetime(2026, 5, 6, 10, 0, 0, tzinfo=UTC)
    event_start = fake_now + timedelta(minutes=45)
    reader = MagicMock()
    reader.get_upcoming_events.return_value = [_mock_calendar_event("Standup", event_start)]
    sched.attach_calendar_reader(reader)
    with patch("scheduler.proactive.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        events = sched.check_calendar()
    assert len(events) == 1
    assert events[0].kind == TriggerKind.CALENDAR_REMINDER
    assert "Standup" in events[0].message


def test_calendar_reminder_silent_without_reader():
    sched, _ = _make_scheduler()
    events = sched.check_calendar()
    assert events == []


def test_calendar_reminder_does_not_fire_outside_1h_window():
    sched, _ = _make_scheduler()
    fake_now = datetime(2026, 5, 6, 10, 0, 0, tzinfo=UTC)
    event_start = fake_now + timedelta(hours=2)
    reader = MagicMock()
    reader.get_upcoming_events.return_value = [_mock_calendar_event("Meeting", event_start)]
    sched.attach_calendar_reader(reader)
    with patch("scheduler.proactive.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        events = sched.check_calendar()
    assert events == []


def test_calendar_reminder_handles_reader_exception_gracefully():
    sched, _ = _make_scheduler()
    reader = MagicMock()
    reader.get_upcoming_events.side_effect = RuntimeError("calendar unavailable")
    sched.attach_calendar_reader(reader)
    # should not raise
    events = sched.check_calendar()
    assert events == []


# ──────────────────────────────────────────────────────────────────────────────
# do_not_disturb — all triggers silent
# ──────────────────────────────────────────────────────────────────────────────


def test_dnd_silences_file_modification_notification():
    sched, sink = _make_scheduler(dnd=True)
    for _ in range(5):
        sched.record_file_modification("/notes/daily.md")
    sink.notify.assert_not_called()


def test_dnd_silences_document_indexed_notification():
    sched, sink = _make_scheduler(dnd=True)
    sched.on_document_indexed("/docs/paper.pdf")
    sink.notify.assert_not_called()


def test_dnd_does_not_suppress_trigger_logic_only_emission():
    """check_file_activity is a pure helper — DND must not suppress its return value."""
    sched, _ = _make_scheduler(dnd=True)
    events = sched.check_file_activity({"/notes/daily.md": 6})
    assert len(events) == 1  # logic still fires; only _emit_all is gated


def test_dnd_tick_does_not_call_sink():
    sched, sink = _make_scheduler(dnd=True)
    sched._tick()
    sink.notify.assert_not_called()


# ──────────────────────────────────────────────────────────────────────────────
# record_activity resets inactivity clock
# ──────────────────────────────────────────────────────────────────────────────


def test_record_activity_resets_clock():
    sched, _ = _make_scheduler()
    old_ts = sched._last_activity
    sched.record_activity()
    assert sched._last_activity >= old_ts
