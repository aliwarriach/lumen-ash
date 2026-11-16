"""The revision plan for the weeks before a test. Pure functions.

Until two weeks before the test nothing changes: the learner just sees the countdown. From then
on each day gets one weak chapter to revise, rotating through the chapters that need work, with
more time as the test gets closer. The same rules feed the daily plan on the Today screen.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from app.exams.readiness import ChapterReadiness

START_DAYS = 14  # revision starts this many days before the test
# (days left at most, minutes a day)
MINUTE_TIERS = [(3, 20), (7, 15), (14, 10)]


class Phase(StrEnum):
    FAR = "far"  # more than two weeks away: only the countdown
    REVISING = "revising"  # inside two weeks: a chapter a day
    TODAY = "today"
    PAST = "past"


@dataclass(frozen=True)
class RevisionDay:
    day: date
    days_left: int
    chapter: ChapterReadiness
    minutes: int


@dataclass(frozen=True)
class Revision:
    phase: Phase
    days_left: int
    schedule: list[RevisionDay]  # today first, then each day until the day before the test

    @property
    def today(self) -> RevisionDay | None:
        """Today's chapter. The schedule only exists inside the revision window and starts today."""
        return self.schedule[0] if self.schedule else None


def minutes_for(days_left: int) -> int:
    for limit, minutes in sorted(MINUTE_TIERS):
        if days_left <= limit:
            return minutes
    return 0


def phase_for(days_left: int) -> Phase:
    if days_left < 0:
        return Phase.PAST
    if days_left == 0:
        return Phase.TODAY
    return Phase.REVISING if days_left <= START_DAYS else Phase.FAR


def revision_plan(today: date, exam_date: date, focus: list[ChapterReadiness]) -> Revision:
    days_left = (exam_date - today).days
    phase = phase_for(days_left)
    schedule: list[RevisionDay] = []
    if phase == Phase.REVISING and focus:
        # Course order, so the rotation doesn't reshuffle when scores change during the day.
        chapters = sorted(focus, key=lambda c: c.number)
        for k in range(days_left):
            left = days_left - k
            if left > START_DAYS:
                continue
            schedule.append(
                RevisionDay(
                    today + timedelta(days=k),
                    left,
                    chapters[left % len(chapters)],
                    minutes_for(left),
                )
            )
    return Revision(phase, days_left, schedule)


def countdown_text(title: str, days_left: int) -> str:
    if days_left < 0:
        return f"{title} was {-days_left} day{'s' if days_left != -1 else ''} ago."
    if days_left == 0:
        return f"{title} is today."
    if days_left == 1:
        return f"{title} is tomorrow."
    return f"{title} is in {days_left} days."


def why_chapter(title: str, days_left: int, chapter: ChapterReadiness) -> str:
    if chapter.score is None:
        about = (
            f"Chapter {chapter.number} has no evidence yet: add its words and answer review cards."
        )
    else:
        about = f"Chapter {chapter.number} is at {round(chapter.score)}%: {chapter.detail}."
    return f"{countdown_text(title, days_left)} {about}"
