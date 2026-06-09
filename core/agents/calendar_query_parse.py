"""Parse date anchors from natural-language calendar read queries."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import StrEnum

_WEEKDAY_BASE_FRAGMENT = (
    r"lunes|martes|mi[eé]rcoles|miercoles|jueves|viernes|s[aá]bado|sabado|domingo|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday"
)
_QUALIFIED_WEEKDAY_FRAGMENT = (
    r"(?:este|esta|pr[oó]ximo|proximo|next|this)\s+" rf"(?:{_WEEKDAY_BASE_FRAGMENT})"
)
_WEEKDAY_FRAGMENT = rf"(?:{_QUALIFIED_WEEKDAY_FRAGMENT}|{_WEEKDAY_BASE_FRAGMENT})"
_REL_DAY_FRAGMENT = r"ma[nñ]ana|manana|tomorrow|hoy|today|pasado\s+ma[nñ]ana|day\s+after\s+tomorrow"
_DATE_TEXT_FRAGMENT = (
    r"\d{1,2}\s+de\s+"
    r"(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|"
    r"octubre|noviembre|diciembre)"
    r"(?:\s+de\s+\d{4})?"
    r"|"
    r"\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?"
    r"|"
    r"\d{1,2}\s+"
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
    r"aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r"(?:\s+\d{4})?"
    r"|"
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
    r"aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+"
    r"\d{1,2}(?:,\s*\d{4})?"
)
_ANCHOR_FRAGMENT = (
    rf"(?:{_WEEKDAY_FRAGMENT}|{_REL_DAY_FRAGMENT}|\d{{4}}-\d{{2}}-\d{{2}}|{_DATE_TEXT_FRAGMENT})"
)
_CALENDAR_CONTEXT_RE = re.compile(
    r"\b(?:calendario|agenda|eventos?|reuniones?|citas?|tengo|hay|calendar|schedule|meetings?)\b",
    re.IGNORECASE,
)
_LOOSE_ON_RE = re.compile(
    r"\b(?:para(?:\s+el|\s+la)?|el|la|on)\s+(?P<fragment>.+?)\s*$",
    re.IGNORECASE,
)
_TRAILING_CALENDAR_CONTEXT_RE = re.compile(
    r"\b(?:en\s+(?:mi\s+)?(?:calendario|agenda)|in\s+(?:my\s+)?(?:calendar|schedule))\b.*$",
    re.IGNORECASE,
)
_SPANISH_WEEKDAY_TO_EN: dict[str, str] = {
    "lunes": "monday",
    "martes": "tuesday",
    "miercoles": "wednesday",
    "miércoles": "wednesday",
    "jueves": "thursday",
    "viernes": "friday",
    "sabado": "saturday",
    "sábado": "saturday",
    "domingo": "sunday",
}

_AFTER_RE = re.compile(
    rf"\b(?:despu[eé]s|despues|tras|after|following)\s+"
    rf"(?:de(?:l|l\s+la)?\s+)?"
    rf"({_ANCHOR_FRAGMENT}|.+?)"
    rf"(?:\s+a\s+las\s+[\d:hapm\.]+)?",
    re.IGNORECASE,
)

_BEFORE_RE = re.compile(
    rf"\b(?:antes|before|until|hasta)\s+" rf"(?:de(?:l|l\s+la)?\s+)?" rf"({_ANCHOR_FRAGMENT})",
    re.IGNORECASE,
)

_ON_RE = re.compile(
    rf"\b(?:"
    rf"(?:qu[eé]|que)\s+tengo\s+(?:el|la|para(?:\s+el|\s+la)?)\s+|"
    rf"(?:qu[eé]|que)\s+hay\s+(?:el|para(?:\s+el|\s+la)?)\s+|"
    rf"eventos?\s+(?:del|de\s+el|para(?:\s+el|\s+la)?|el)\s+|"
    rf"reuniones?\s+(?:del|de\s+el|para(?:\s+el|\s+la)?|el)\s+|"
    rf"citas?\s+(?:del|de\s+el|para(?:\s+el|\s+la)?|el)\s+|"
    rf"agenda\s+(?:del|de|para(?:\s+el|\s+la)?)\s+|"
    rf"calendario\s+(?:del|de|para(?:\s+el|\s+la)?)\s+|"
    rf"para(?:\s+el|\s+la)?\s+|"
    rf"on\s+"
    rf")"
    rf"({_ANCHOR_FRAGMENT})",
    re.IGNORECASE,
)

# "eventos del jueves", "reuniones del viernes"
_ON_SHORT_RE = re.compile(
    rf"\b(?:eventos?|reuniones?|citas?|agenda|calendario)\s+del?\s+"
    rf"({_WEEKDAY_FRAGMENT}|{_REL_DAY_FRAGMENT}|{_DATE_TEXT_FRAGMENT})\b",
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
    parsed = _parse_event_datetime(text)
    if parsed is not None:
        return parsed
    normalized = _normalize_spanish_weekday_hint(text)
    if normalized == text:
        return None
    return _parse_event_datetime(normalized)


def _normalize_spanish_weekday_hint(text: str) -> str:
    raw = text.strip()
    lowered = raw.lower()
    if not lowered:
        return raw

    match = re.match(
        r"^(?:(este|esta|pr[oó]ximo|proximo)\s+)?(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)$",
        lowered,
    )
    if not match:
        return raw

    qualifier, weekday = match.groups()
    weekday_en = _SPANISH_WEEKDAY_TO_EN.get(weekday, weekday)
    if qualifier in {"este", "esta", "próximo", "proximo"}:
        return weekday_en
    return weekday_en


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
    loose = _extract_loose_on_filter(text)
    if loose is not None:
        return loose
    return None


def _extract_loose_on_filter(text: str) -> CalendarDateFilter | None:
    """Fallback parser for day-scoped asks not covered by strict regex patterns."""
    if not _CALENDAR_CONTEXT_RE.search(text):
        return None
    cleaned = _TRAILING_CALENDAR_CONTEXT_RE.sub("", text).strip().rstrip("?.!")
    m = _LOOSE_ON_RE.search(cleaned)
    if not m:
        return None
    fragment = m.group("fragment").strip()
    if not fragment:
        return None
    anchor_day, anchor_dt = _anchor_day_from_fragment(fragment)
    if anchor_day is None:
        return None
    return CalendarDateFilter(
        kind=DateFilterKind.ON,
        anchor_day=anchor_day,
        anchor_label=_format_anchor_label(anchor_day),
        has_time=anchor_dt is not None,
        anchor_dt=anchor_dt,
    )


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


def hours_window_for_filter(
    date_filter: CalendarDateFilter | None,
    *,
    base_hours: int,
    lookahead_days_after: int = 30,
    max_days: int = 370,
) -> int:
    """Expand search window so day-scoped queries include the requested date."""
    if date_filter is None:
        return max(1, base_hours)

    local = _local_tz()
    now = datetime.now().astimezone(local)
    max_hours = 24 * max_days

    def _clamp(hours: int) -> int:
        return max(1, min(hours, max_hours))

    if date_filter.kind == DateFilterKind.ON:
        end = datetime.combine(
            date_filter.anchor_day, time.max.replace(microsecond=0), tzinfo=local
        )
    elif date_filter.kind == DateFilterKind.BEFORE:
        if date_filter.has_time and date_filter.anchor_dt is not None:
            end = date_filter.anchor_dt.astimezone(local)
        else:
            end = datetime.combine(date_filter.anchor_day, time.min, tzinfo=local)
    else:  # AFTER
        if date_filter.has_time and date_filter.anchor_dt is not None:
            anchor = date_filter.anchor_dt.astimezone(local)
        else:
            anchor = datetime.combine(
                date_filter.anchor_day, time.max.replace(microsecond=0), tzinfo=local
            )
        end = anchor + timedelta(days=lookahead_days_after)

    delta_hours = int((end - now).total_seconds() // 3600) + 1
    return max(base_hours, _clamp(delta_hours))
