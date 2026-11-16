"""Turns the date words in a class message into a real date. Pure functions, no AI.

The AI only copies the words ("Freitag", "15.12.", "in 3 Tagen"); the arithmetic is done here, so
a date is never a guess. German and English are understood. Anything unclear gives None and the
learner picks the date themselves.

Rules worth knowing:
- Dates are day-first: 12.11. and 12/11 are 12 November.
- A date without a year is this year, unless that is more than 60 days ago: then it is next year.
- A weekday means the next one, after today: on a Friday, "Freitag" is a week away, and "heute"
  or "today" means today. "diesen Freitag" / "this Friday" may be today.
- "nächste Woche Montag" is the Monday of next calendar week.
- Times of day are ignored: only the date is kept.
- A full date beats a relative word ("Freitag, 14.11." is 14 November).
"""

import re
from collections.abc import Callable
from datetime import date, timedelta

_WEEKDAYS = {
    "montag": 0,
    "monday": 0,
    "dienstag": 1,
    "tuesday": 1,
    "mittwoch": 2,
    "wednesday": 2,
    "donnerstag": 3,
    "thursday": 3,
    "freitag": 4,
    "friday": 4,
    "samstag": 5,
    "sonnabend": 5,
    "saturday": 5,
    "sonntag": 6,
    "sunday": 6,
}
_MONTHS = {
    "januar": 1,
    "jänner": 1,
    "january": 1,
    "februar": 2,
    "february": 2,
    "märz": 3,
    "maerz": 3,
    "march": 3,
    "april": 4,
    "mai": 5,
    "may": 5,
    "juni": 6,
    "june": 6,
    "juli": 7,
    "july": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "october": 10,
    "november": 11,
    "dezember": 12,
    "december": 12,
}
_WEEKDAY = "|".join(sorted(_WEEKDAYS, key=len, reverse=True))
_MONTH = "|".join(sorted(_MONTHS, key=len, reverse=True))
_FLAGS = re.IGNORECASE

_ISO = re.compile(r"(?<![\d-])(\d{4})-(\d{1,2})-(\d{1,2})(?![\d-])")
# 12.11.2026, 12.11.26, 12.11. and 12/11. Not "10.30 Uhr" (a time) and not part of a longer number.
_NUMERIC = re.compile(
    r"(?<![\d.,/])(\d{1,2})[./](\d{1,2})(?:[./](\d{4}|\d{2})(?!\d))?(?![\d/])"
    r"(?!\s*(?:uhr\b|h\b|am\b|pm\b|o'clock))",
    _FLAGS,
)
# 15. Dezember [2026], 15 December, 15th of December
_DAY_MONTH = re.compile(
    rf"(?<!\d)(\d{{1,2}})\.?(?:st|nd|rd|th)?\s+(?:of\s+)?({_MONTH})\b(?:,?\s+(\d{{4}})(?!\d))?",
    _FLAGS,
)
# December 15, December 15th 2026
_MONTH_DAY = re.compile(
    rf"\b({_MONTH})\s+(\d{{1,2}})(?!\d)(?:st|nd|rd|th)?(?:,?\s+(\d{{4}})(?!\d))?",
    _FLAGS,
)
_NEXT_WEEK_DAY = re.compile(
    rf"\b(?:n(?:ä|ae)chste[nrms]?|kommende[nrms]?|next)\s+(?:woche|week)\s*,?\s*"
    rf"(?:am\s+|on\s+)?({_WEEKDAY})\b",
    _FLAGS,
)
_THIS_WEEKDAY = re.compile(rf"\b(?:diese[nrms]?|this)\s+({_WEEKDAY})\b", _FLAGS)
_WEEKDAY_WORD = re.compile(rf"\b({_WEEKDAY})\b", _FLAGS)
_IN_N = re.compile(
    r"\b(?:in|within|innerhalb von)\s+(\d{1,2}|einem|einer|one|a|zwei|two|drei|three)\s+"
    r"(tag(?:en|e)?|days?|woche[n]?|weeks?)\b",
    _FLAGS,
)
_TODAY = re.compile(r"\b(heute|today)\b", _FLAGS)
_DAY_AFTER = re.compile(r"\b(?:übermorgen|uebermorgen|day after tomorrow)\b", _FLAGS)
_TOMORROW = re.compile(r"\b(morgen|tomorrow)\b", _FLAGS)
# "guten Morgen" and "am Morgen" are the morning, not tomorrow.
_MORNING_BEFORE = re.compile(r"(?:guten|jeden|good|am|heute|gestern|every)\s*$", _FLAGS)
_WEEKDAY_BEFORE = re.compile(rf"\b(?:{_WEEKDAY})\s*,?\s*$", _FLAGS)
_WORD_NUMBERS = {
    "einem": 1,
    "einer": 1,
    "one": 1,
    "a": 1,
    "zwei": 2,
    "two": 2,
    "drei": 3,
    "three": 3,
}

_MAX_PAST_DAYS_SAME_YEAR = 60


def _safe(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _year(day: int, month: int, today: date) -> date | None:
    """A date with no year: this year, or next if this year's is long gone."""
    here = _safe(today.year, month, day)
    if here is None:
        return None
    if (today - here).days > _MAX_PAST_DAYS_SAME_YEAR:
        return _safe(today.year + 1, month, day)
    return here


def _explicit_year(raw: str) -> int:
    year = int(raw)
    return 2000 + year if year < 100 else year


def _next_weekday(today: date, weekday: int, *, allow_today: bool = False) -> date:
    ahead = (weekday - today.weekday()) % 7
    if ahead == 0 and not allow_today:
        ahead = 7
    return today + timedelta(days=ahead)


def _absolute(text: str, today: date) -> list[tuple[int, date]]:
    found: list[tuple[int, date]] = []
    for m in _ISO.finditer(text):
        if d := _safe(int(m[1]), int(m[2]), int(m[3])):
            found.append((m.start(), d))
    for m in _NUMERIC.finditer(text):
        day, month = int(m[1]), int(m[2])
        d = (
            _safe(_explicit_year(m[3]), month, day)
            if m[3]
            else _year(day, month, today)
            if 1 <= month <= 12
            else None
        )
        if d:
            found.append((m.start(), d))
    for m in _DAY_MONTH.finditer(text):
        day, month = int(m[1]), _MONTHS[m[2].lower()]
        d = _safe(_explicit_year(m[3]), month, day) if m[3] else _year(day, month, today)
        if d:
            found.append((m.start(), d))
    for m in _MONTH_DAY.finditer(text):
        day, month = int(m[2]), _MONTHS[m[1].lower()]
        d = _safe(_explicit_year(m[3]), month, day) if m[3] else _year(day, month, today)
        if d:
            found.append((m.start(), d))
    return found


def _relative(text: str, today: date) -> list[tuple[int, date]]:
    found: list[tuple[int, date]] = []
    taken: list[tuple[int, int]] = []  # spans already explained, so a weekday isn't read twice

    def add(pattern: re.Pattern[str], make: Callable[[re.Match[str]], date | None]) -> None:
        for m in pattern.finditer(text):
            if any(start <= m.start() < end for start, end in taken):
                continue
            if (d := make(m)) is not None:
                found.append((m.start(), d))
                taken.append((m.start(), m.end()))

    def next_week(m: re.Match[str]) -> date:
        monday = today - timedelta(days=today.weekday()) + timedelta(days=7)
        return monday + timedelta(days=_WEEKDAYS[m[1].lower()])

    def in_n(m: re.Match[str]) -> date:
        raw = m[1].lower()
        n = int(raw) if raw.isdigit() else _WORD_NUMBERS[raw]
        weeks = m[2].lower().startswith(("w",))
        return today + timedelta(days=n * (7 if weeks else 1))

    add(_NEXT_WEEK_DAY, next_week)
    add(_IN_N, in_n)
    add(_THIS_WEEKDAY, lambda m: _next_weekday(today, _WEEKDAYS[m[1].lower()], allow_today=True))
    add(_WEEKDAY_WORD, lambda m: _next_weekday(today, _WEEKDAYS[m[1].lower()]))
    add(_DAY_AFTER, lambda m: today + timedelta(days=2))
    add(_TODAY, lambda m: today)

    def tomorrow(m: re.Match[str]) -> date | None:
        before = text[: m.start()]
        if _MORNING_BEFORE.search(before):
            return None
        if _WEEKDAY_BEFORE.search(before):  # "Freitag morgen" is Friday morning
            return None
        return today + timedelta(days=1)

    add(_TOMORROW, tomorrow)
    return found


def parse_due(text: str, today: date) -> date | None:
    """The date `text` points to, or None if it names none. `today` is the learner's local date."""
    if not text or not text.strip():
        return None
    absolute = _absolute(text, today)
    if absolute:
        return min(absolute, key=lambda f: f[0])[1]
    relative = _relative(text, today)
    if relative:
        return min(relative, key=lambda f: f[0])[1]
    return None
