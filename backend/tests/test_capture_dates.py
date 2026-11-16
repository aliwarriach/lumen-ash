from datetime import date

import pytest

from app.capture.dates import parse_due

TODAY = date(2026, 11, 11)  # a Wednesday


def d(month: int, day: int, year: int = 2026) -> date:
    return date(year, month, day)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Relative words, German and English
        ("heute", TODAY),
        ("today", TODAY),
        ("morgen", d(11, 12)),
        ("Test morgen früh", d(11, 12)),
        ("tomorrow", d(11, 12)),
        ("übermorgen", d(11, 13)),
        ("the day after tomorrow", d(11, 13)),
        # A weekday is the next one: on a Wednesday, "Mittwoch" is a week away
        ("Freitag", d(11, 13)),
        ("bis Freitag", d(11, 13)),
        ("am Montag", d(11, 16)),
        ("by Monday", d(11, 16)),
        ("Mittwoch", d(11, 18)),
        ("diesen Mittwoch", TODAY),
        ("this Friday", d(11, 13)),
        ("nächsten Montag", d(11, 16)),
        ("next Monday", d(11, 16)),
        ("nächste Woche Montag", d(11, 16)),
        ("next week Friday", d(11, 20)),
        ("Sonntag", d(11, 15)),
        # "morgen" after a weekday, or after "guten", is the morning
        ("Freitag morgen", d(11, 13)),
        ("Guten Morgen", None),
        # Numeric dates are day-first
        ("14.11.", d(11, 14)),
        ("14.11.2026", d(11, 14)),
        ("14.11.26", d(11, 14)),
        ("14/11/2026", d(11, 14)),
        ("14/11", d(11, 14)),
        ("2026-12-01", d(12, 1)),
        ("bis 3.12.", d(12, 3)),
        # No year: this year, unless that is long past
        ("10.11.", d(11, 10)),  # yesterday: overdue, still this year
        ("05.01.", d(1, 5, 2027)),
        ("31.12.", d(12, 31)),
        # Month names
        ("15. Dezember", d(12, 15)),
        ("15 December", d(12, 15)),
        ("15th of December", d(12, 15)),
        ("December 15", d(12, 15)),
        ("December 15th, 2027", d(12, 15, 2027)),
        ("1. März 2027", d(3, 1, 2027)),
        # "in N days/weeks"
        ("in 3 Tagen", d(11, 14)),
        ("in 2 days", d(11, 13)),
        ("in einer Woche", d(11, 18)),
        ("in 2 Wochen", d(11, 25)),
        # A full date beats a weekday, whichever comes first
        ("Freitag, 20.11.", d(11, 20)),
        ("20.11. (Freitag)", d(11, 20)),
        ("am Freitag, den 20. November", d(11, 20)),
    ],
)
def test_understood_dates(text: str, expected: date | None) -> None:
    assert parse_due(text, TODAY) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "bald",
        "nächste Woche",  # no day named: not a date
        "next week",
        "31.02.",  # not a real date
        "32.1.",
        "13.13.",
        "um 10.30 Uhr",  # a time, not 10 March
        "um 9.15",
        "Seite 24",
        "Do",  # abbreviations are too ambiguous to read
        "so",
    ],
)
def test_text_that_is_not_a_date_gives_none(text: str) -> None:
    assert parse_due(text, TODAY) is None


def test_a_leap_day_is_only_valid_in_a_leap_year() -> None:
    assert parse_due("29.2.2028", TODAY) == date(2028, 2, 29)
    assert parse_due("29.2.2027", TODAY) is None


def test_the_result_depends_on_the_learners_today_not_the_servers() -> None:
    assert parse_due("morgen", date(2026, 12, 31)) == date(2027, 1, 1)
    assert parse_due("Freitag", date(2026, 11, 13)) == date(2026, 11, 20)  # today is Friday
    assert parse_due("this Friday", date(2026, 11, 13)) == date(2026, 11, 13)
