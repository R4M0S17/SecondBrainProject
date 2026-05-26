"""Parse date anchors from natural-language calendar read queries."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import StrEnum

_WEEKDAY_FRAGMENT = (
    r"lunes|martes|mi[eé]rcoles|miercoles|jueves|viernes|s[aá]bado|sabado|domingo|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday"
)
_REL_DAY_FRAGMENT = r"ma[nñ]ana|manana|tomorrow|hoy|today|pasado\s+ma[nñ]ana|day\s+after\s+tomorrow"

_AFTER_RE = re.compile(
    rf"\b(?:despu[eé]s|despues|tras|after|following)\s+"
    rf"(?:de(?:l|l\s+la)?\s+)?"
    rf"({_WEEKDAY_FRAGMENT}|{_REL_DAY_FRAGMENT}|\d{{4}}-\d{{2}}-\d{{2}}|.+?)"
    rf"(?:\s+a\s+las\s+[\d:hapm\.]+)?",
    re.IGNORECASE,
)

_BEFORE_RE = re.compile(
    rf"\b(?:antes|before|until|hasta)\s+"
    rf"(?:de(?:l|l\s+la)?\s+)?"
    rf"({_WEEKDAY_FRAGMENT}|{_REL_DAY_FRAGMENT}|\d{{4}}-\d{{2}}-\d{{2}})",
    re.IGNORECASE,
)

_ON_RE = re.compile(
    rf"\b(?:"
    rf"(?:qu[eé]|que)\s+tengo\s+(?:el|para\s+el|para\s+la)\s+|"
    rf"(?:qu[eé]|que)\s+hay\s+(?:el|para\s+el)\s+|"
    rf"eventos?\s+(?:del|de\s+el|para\s+el|el)\s+|"
    rf"reuniones?\s+(?:del|de\s+el|para\s+el|el)\s+|"
    rf"citas?\s+(?:del|de\s+el|para\s+el|el)\s+|"
    rf"agenda\s+(?:del|de|para\s+el)\s+|"
    rf"calendario\s+(?:del|de|para\s+el)\s+|"
    rf"para\s+el\s+|"
    rf"on\s+"
    rf")"
    rf"({_WEEKDAY_FRAGMENT}|{_REL_DAY_FRAGMENT}|\d{{4}}-\d{{2}}-\d{{2}})",
    re.IGNORECASE,
)

# "eventos del jueves", "reuniones del viernes"
_ON_SHORT_RE = re.compile(
    rf"\b(?:eventos?|reuniones?|citas?|agenda|calendario)\s+del?\s+"
    rf"({_WEEKDAY_FRAGMENT}|{_REL_DAY_FRAGMENT})\b",
    re.IGNORECASE,
)


class DateFilterKind(StrEnum):
    AFTER = "after"
    BEFORE = "before"
    ON = "on"


@dataclass(frozen=True)
class CalendarDateFilter:
    kind: DateFilterKind
    anchor_day: date
    anchor_label: str
    has_time: bool = False
    anchor_dt: datetime | None = None


def _local_tz():
    from core.tools.handlers.calendar import _local_tz as _tz

    return _tz()


def _parse_anchor_fragment(fragment: str) -> datetime | None:
    from core.tools.handlers.calendar import _parse_event_datetime

    text = fragment.strip().rstrip("?.!")
    if not text:
        return None
    return _parse_event_datetime(text)


def _format_anchor_label(anchor_day: date) -> str:
    local = _local_tz()
    dt = datetime.combine(anchor_day, time(12, 0), tzinfo=local)
    return dt.strftime("%A %d de %B de %Y")


def _anchor_day_from_fragment(fragment: str) -> tuple[date | None, datetime | None]:
    parsed = _parse_anchor_fragment(fragment)
    if parsed is None:
        return None, None
    local = parsed.astimezone(_local_tz())
    has_time = not (
        local.hour == 0 and local.minute == 0 and local.second == 0 and local.microsecond == 0
    )
    return local.date(), local if has_time else None


def extract_calendar_date_filter(query: str) -> CalendarDateFilter | None:
    """Return a date window filter if the query scopes events to a day anchor."""
    text = query.strip()
    if not text:
        return None

    for regex, kind in (
        (_AFTER_RE, DateFilterKind.AFTER),
        (_BEFORE_RE, DateFilterKind.BEFORE),
        (_ON_RE, DateFilterKind.ON),
        (_ON_SHORT_RE, DateFilterKind.ON),
    ):
        m = regex.search(text)
        if not m:
            continue
        fragment = m.group(1).strip()
        anchor_day, anchor_dt = _anchor_day_from_fragment(fragment)
        if anchor_day is None:
            continue
        label = _format_anchor_label(anchor_day)
        return CalendarDateFilter(
            kind=kind,
            anchor_day=anchor_day,
            anchor_label=label,
            has_time=anchor_dt is not None,
            anchor_dt=anchor_dt,
        )
    return None


def filter_events_by_date(
    events: list,
    date_filter: CalendarDateFilter | None,
) -> list:
    """Apply after/before/on filtering to calendar events (sorted by start)."""
    if date_filter is None:
        return sorted(events, key=lambda ev: ev.start)

    local = _local_tz()
    kind = date_filter.kind
    day = date_filter.anchor_day

    if kind == DateFilterKind.ON:
        start_bound = datetime.combine(day, time.min, tzinfo=local)
        end_bound = datetime.combine(day, time.max.replace(microsecond=0), tzinfo=local)
    elif kind == DateFilterKind.AFTER:
        if date_filter.has_time and date_filter.anchor_dt is not None:
            start_bound = date_filter.anchor_dt.astimezone(local)
        else:
            start_bound = datetime.combine(day, time.max.replace(microsecond=0), tzinfo=local)
        end_bound = None
    else:  # BEFORE
        if date_filter.has_time and date_filter.anchor_dt is not None:
            end_bound = date_filter.anchor_dt.astimezone(local)
        else:
            end_bound = datetime.combine(day, time.min, tzinfo=local)
        start_bound = None

    filtered: list = []
    for ev in events:
        start = ev.start.astimezone(local)
        if kind == DateFilterKind.ON:
            end = end_bound
            assert end is not None
            if start_bound <= start <= end + timedelta(seconds=1):
                filtered.append(ev)
        elif kind == DateFilterKind.AFTER:
            if start > start_bound:
                filtered.append(ev)
        else:
            if start < end_bound:
                filtered.append(ev)
    return sorted(filtered, key=lambda ev: ev.start)


def scope_phrase_for_filter(date_filter: CalendarDateFilter | None) -> str:
    if date_filter is None:
        return ""
    if date_filter.kind == DateFilterKind.AFTER:
        return f"después del {date_filter.anchor_label}"
    if date_filter.kind == DateFilterKind.BEFORE:
        return f"antes del {date_filter.anchor_label}"
    return f"el {date_filter.anchor_label}"
