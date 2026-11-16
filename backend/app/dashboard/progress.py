"""Streak and "am I on track?", from the days the learner studied. Pure functions.

A day counts as studied if the learner answered a review, checked some writing, or marked a
chapter resource done. Days are the learner's own local dates.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

# More cards than this waiting means reviews are piling up faster than they are cleared.
BACKLOG_CARDS = 40
WINDOW_DAYS = 7
# On track = studied on at least this share of the days in the window.
ON_TRACK_SHARE = 0.6
MAX_GAP_DAYS = 2  # missing this many days in a row is "slipping"


class TrackStatus(StrEnum):
    GETTING_STARTED = "getting_started"
    ON_TRACK = "on_track"
    SLIPPING = "slipping"


@dataclass(frozen=True)
class Progress:
    status: TrackStatus
    reason: str
    streak: int
    days_studied: int  # in the last 7 days
    last_studied: date | None


def streak(days: set[date], today: date) -> int:
    """Consecutive studied days. Today not being studied yet doesn't break it: it ends
    yesterday and only breaks if yesterday was missed too."""
    day = today if today in days else today - timedelta(days=1)
    count = 0
    while day in days:
        count += 1
        day -= timedelta(days=1)
    return count


def week_studied(days: set[date], today: date) -> list[date]:
    """The days studied in this calendar week (Monday to today), in order: the week strip."""
    monday = today - timedelta(days=today.weekday())
    return sorted(d for d in days if monday <= d <= today)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def assess(days: set[date], today: date, cards_due: int) -> Progress:
    window_start = today - timedelta(days=WINDOW_DAYS - 1)
    studied = len([d for d in days if window_start <= d <= today])
    current = streak(days, today)
    last = max(days, default=None)

    if last is None:
        return Progress(
            TrackStatus.GETTING_STARTED,
            "Nothing studied yet. Do today's plan and your streak starts.",
            0,
            0,
            None,
        )

    gap = (today - last).days
    if gap >= MAX_GAP_DAYS:
        reason = f"You last studied {_plural(gap, 'day')} ago. A short session today gets you back."
        return Progress(TrackStatus.SLIPPING, reason, current, studied, last)
    if cards_due > BACKLOG_CARDS:
        reason = f"{cards_due} cards are waiting. Clearing them first keeps reviews short."
        return Progress(TrackStatus.SLIPPING, reason, current, studied, last)

    # A new learner is judged on the days they have actually had, not on a full week.
    days_available = min(WINDOW_DAYS, (today - min(days)).days + 1)
    needed = max(1, round(days_available * ON_TRACK_SHARE))
    if studied < needed:
        reason = f"You studied on {studied} of the last {days_available} days. Aim for {needed}."
        return Progress(TrackStatus.SLIPPING, reason, current, studied, last)
    reason = f"You studied on {studied} of the last {days_available} days"
    reason += f", {_plural(current, 'day')} in a row." if current > 1 else "."
    return Progress(TrackStatus.ON_TRACK, reason, current, studied, last)
