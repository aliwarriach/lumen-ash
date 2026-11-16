"""Writes the progress review from the learner's numbers. Plain rules and fixed sentences: no AI.

Tone, decided only from real numbers:
  start         nothing studied yet: a warm welcome and the first step
  welcome_back  studied before, but not in the last 7 days: no blame, just how to restart
  great         studied often and answers mostly right
  good          a solid week, with one concrete way to make it better
  keep_going    answers mostly wrong: honest, constructive, and encouraging. Never praise.

Praise is only ever given for something that really went well (a streak, more days than last
week, a high share of right answers, words saved or mastered, lessons completed). A drop is shown
as a plain number and never praised.
"""

from dataclasses import dataclass
from enum import StrEnum


class Tone(StrEnum):
    START = "start"
    WELCOME_BACK = "welcome_back"
    GREAT = "great"
    GOOD = "good"
    KEEP_GOING = "keep_going"


@dataclass(frozen=True)
class Numbers:
    studied_ever: bool
    days_this_week: int
    days_last_week: int
    streak: int
    cards_this_week: int
    cards_last_week: int
    answers_this_week: int  # checked answers: review cards and grammar practice
    right_this_week: int
    words_total: int
    words_added_this_week: int
    words_mastered: int
    lessons_completed: int  # sentence lessons with a best round of 80% or more
    rules_strong: int  # grammar rules at 90%+ over 30 days
    resources_done_this_week: int


# Below this many checked answers in a week, the share of right answers says too little to judge.
MIN_ANSWERS = 8
GREAT_FROM = 0.85
GOOD_FROM = 0.7
WORD_MILESTONES = (250, 100, 50, 25, 10)
MAX_ACHIEVEMENTS = 6


def accuracy(n: Numbers) -> float | None:
    if n.answers_this_week < MIN_ANSWERS:
        return None
    return n.right_this_week / n.answers_this_week


def _plural(n: int, word: str, plural: str | None = None) -> str:
    return f"{n} {word if n == 1 else (plural or word + 's')}"


def tone(n: Numbers) -> Tone:
    if not n.studied_ever:
        return Tone.START
    if n.days_this_week == 0:
        return Tone.WELCOME_BACK
    acc = accuracy(n)
    if acc is not None and acc < GOOD_FROM:
        return Tone.KEEP_GOING
    if n.days_this_week >= 4 and (acc is None or acc >= GREAT_FROM):
        return Tone.GREAT
    return Tone.GOOD


def headline_and_message(n: Numbers) -> tuple[Tone, str, str]:
    t = tone(n)
    acc = accuracy(n)
    if t is Tone.START:
        return (
            t,
            "Let's get started!",
            (
                "Your first step: the Kapitel 1 sentence lesson or a grammar practice. Ten minutes "
                "a day is enough, and everything you do shows up here."
            ),
        )
    if t is Tone.WELCOME_BACK:
        return (
            t,
            "Good to see you again!",
            (
                "You haven't studied in the last 7 days. That happens to everyone, and nothing "
                "is lost: your words and progress are all still here. Start small today with "
                "one short lesson or your review cards."
            ),
        )
    if t is Tone.KEEP_GOING:
        pct = round((acc or 0) * 100)
        return (
            t,
            "Keep going: this is how learning works",
            (
                f"{pct}% of your answers were right this week. That means the material is still "
                "new to you, which is completely normal. Slow down, open the hints before you "
                "answer, and repeat the lessons you found hard. Don't give up: every round makes "
                "the next one easier."
            ),
        )
    if t is Tone.GREAT:
        return (
            t,
            "Fantastic week!",
            (
                f"You studied on {_plural(n.days_this_week, 'day')} and kept your answers right. "
                "This is exactly how German sticks. Keep it up!"
            ),
        )
    # GOOD: honest praise plus the one change that would help most.
    if n.days_this_week < 3:
        tip = (
            "Studying a little on 3 or 4 days a week helps more than one long session. Can you "
            "add one more short day?"
        )
    elif acc is not None and acc < GREAT_FROM:
        tip = "Use the hints on the questions you get wrong: they make the rule stick."
    else:
        tip = "Try the next lesson: you're ready for it."
    return t, "Good work this week", (f"You studied on {_plural(n.days_this_week, 'day')}. {tip}")


def achievements(n: Numbers) -> list[str]:
    """Only real positives, most motivating first."""
    out: list[str] = []
    if n.streak >= 3:
        out.append(f"🔥 {n.streak}-day streak!")
    if n.days_this_week > n.days_last_week and n.days_last_week > 0:
        more = n.days_this_week - n.days_last_week
        out.append(f"You studied on {_plural(more, 'more day')} than last week.")
    acc = accuracy(n)
    if acc is not None and acc >= GREAT_FROM:
        out.append(f"{round(acc * 100)}% of your answers were right this week.")
    if n.cards_this_week > 0:
        text = f"You reviewed {_plural(n.cards_this_week, 'card')} this week"
        if n.cards_this_week > n.cards_last_week and n.cards_last_week > 0:
            text += f", {n.cards_this_week - n.cards_last_week} more than last week"
        out.append(text + ".")
    if n.words_added_this_week > 0:
        out.append(f"{_plural(n.words_added_this_week, 'new word')} saved this week.")
    for milestone in WORD_MILESTONES:
        if n.words_total >= milestone:
            out.append(f"You have collected {milestone}+ words!")
            break
    if n.words_mastered > 0:
        out.append(f"{_plural(n.words_mastered, 'word')} mastered: you can use them in sentences.")
    if n.lessons_completed > 0:
        out.append(f"{_plural(n.lessons_completed, 'sentence lesson')} completed.")
    if n.rules_strong > 0:
        out.append(f"{_plural(n.rules_strong, 'grammar rule')} already strong (90%+).")
    if n.resources_done_this_week > 0:
        out.append(f"{_plural(n.resources_done_this_week, 'course item')} done this week.")
    return out[:MAX_ACHIEVEMENTS]


def change_text(this: int, last: int) -> tuple[str, bool | None]:
    """'+3 on last week' (good), 'same as last week', or '2 fewer than last week' (a plain fact,
    neither praised nor scolded). The flag is True for a rise, None otherwise."""
    if this > last:
        return f"+{this - last} on last week", True
    if this == last:
        return "same as last week", None
    return f"{last - this} fewer than last week", None
