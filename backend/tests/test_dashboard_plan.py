import uuid
from datetime import date, timedelta

from app.dashboard.plan import (
    ClassTaskInfo,
    GrammarPick,
    PlanInputs,
    PlanItem,
    PlanKind,
    ResourceInfo,
    ReviewInfo,
    TaskInfo,
    build_plan,
)
from app.dashboard.progress import BACKLOG_CARDS, TrackStatus, assess, streak, week_studied
from app.grammar.catalog import PatternKey

NOTHING = ReviewInfo(due=0, new=0, retries_due=0, reviewed_today=0)


def resource(number: int = 3, title: str = "Übung", ref: str | None = "S. 24") -> ResourceInfo:
    return ResourceInfo(uuid.uuid4(), uuid.uuid4(), number, title, ref, "https://example.com/x")


def kinds(inputs: PlanInputs) -> list[PlanKind]:
    return [i.kind for i in build_plan(inputs).items]


def chat_task(days_left: int, title: str = "Aufgabe", done_today: bool = False) -> ClassTaskInfo:
    return ClassTaskInfo(uuid.uuid4(), title, days_left, None, done_today)


# --- The plan ----------------------------------------------------------------------------------


def test_a_brand_new_learner_gets_a_short_honest_plan() -> None:
    plan = build_plan(PlanInputs(review=NOTHING))
    assert [i.kind for i in plan.items] == [PlanKind.WRITING, PlanKind.LISTENING, PlanKind.SPEAKING]
    assert plan.total_minutes == 23 and plan.note == (
        "A light day: everything that is pending is in the plan."
    )
    assert all(i.why for i in plan.items)  # every item says why
    assert [i.done for i in plan.items] == [False, None, None]  # writing is tracked, the rest not


def test_every_item_says_why_and_ids_are_unique_and_stable() -> None:
    inputs = PlanInputs(
        review=ReviewInfo(due=12, new=5, retries_due=3, reviewed_today=0),
        grammar=GrammarPick(PatternKey.ACCUSATIVE, "Accusative", "4 wrong out of 10.", False),
        homework_pending=[resource()],
        listening_pending=resource(title="Dialog"),
        writing_task=TaskInfo(uuid.uuid4(), "5 sentences about your day", 5),
        speaking_words=["der Tisch"],
    )
    plan = build_plan(inputs)
    assert [i.kind for i in plan.items] == [
        PlanKind.REVIEW,
        PlanKind.GRAMMAR,
        PlanKind.HOMEWORK,
        PlanKind.WRITING,
        PlanKind.LISTENING,
        PlanKind.SPEAKING,
    ]
    assert all(i.why.strip() for i in plan.items)
    ids = [i.id for i in plan.items]
    assert len(set(ids)) == len(ids)
    assert [i.id for i in build_plan(inputs).items] == ids  # same data, same ids


def test_the_review_item_uses_the_learners_own_numbers() -> None:
    item = build_plan(
        PlanInputs(review=ReviewInfo(due=12, new=5, retries_due=3, reviewed_today=0))
    ).items[0]
    assert item.title == "Review 17 cards"
    assert item.why == "12 cards due, 3 of them mistake retries and 5 new."
    assert item.minutes == 7  # 17 cards at ~24 seconds each

    one = build_plan(PlanInputs(review=ReviewInfo(1, 0, 0, 0))).items[0]
    assert one.title == "Review 1 card" and one.why == "1 card due."
    only_new = build_plan(PlanInputs(review=ReviewInfo(0, 3, 0, 0))).items[0]
    assert only_new.why == "3 new cards to start."


def test_review_time_is_between_five_and_twenty_minutes() -> None:
    assert build_plan(PlanInputs(review=ReviewInfo(2, 0, 0, 0))).items[0].minutes == 5
    assert build_plan(PlanInputs(review=ReviewInfo(500, 0, 0, 0))).items[0].minutes == 20


def test_a_finished_review_stays_in_the_plan_ticked_and_out_of_the_time_left() -> None:
    plan = build_plan(PlanInputs(review=ReviewInfo(0, 0, 0, reviewed_today=14)))
    review = plan.items[0]
    assert (review.kind, review.done) == (PlanKind.REVIEW, True)
    assert review.why == "All done: you reviewed 14 cards today."
    assert plan.remaining_minutes == plan.total_minutes - review.minutes


def test_the_plan_never_goes_over_an_hour_and_names_what_it_left_out() -> None:
    inputs = PlanInputs(
        review=ReviewInfo(due=100, new=0, retries_due=0, reviewed_today=0),  # 20 min
        grammar=GrammarPick(PatternKey.ACCUSATIVE, "Accusative", "Weak.", False),  # 5
        homework_pending=[resource(1), resource(2), resource(3)],  # 2 shown: 20
        writing_task=None,  # 10
        listening_pending=resource(title="Dialog"),  # 8: doesn't fit
        speaking_words=[],  # 5
    )
    plan = build_plan(inputs)
    assert plan.total_minutes == 60
    assert [i.kind for i in plan.items].count(PlanKind.HOMEWORK) == 2
    assert PlanKind.LISTENING not in [i.kind for i in plan.items]
    assert plan.note == "Left for another day to keep it under an hour: listening."


def test_the_most_important_items_win_when_time_is_short() -> None:
    plan = build_plan(
        PlanInputs(
            review=ReviewInfo(due=500, new=0, retries_due=0, reviewed_today=0),
            grammar=GrammarPick(PatternKey.PERFEKT, "Perfekt", "Weak.", False),
            homework_pending=[resource(1), resource(2)],
            homework_done_today=[resource(1), resource(2)],
            writing_task=TaskInfo(uuid.uuid4(), "Task", 5),
        )
    )
    assert plan.total_minutes <= 60
    assert [i.kind for i in plan.items][:2] == [PlanKind.REVIEW, PlanKind.GRAMMAR]


def test_a_grammar_item_links_the_pattern_and_is_done_once_practised_today() -> None:
    pick = GrammarPick(PatternKey.ACCUSATIVE, "Accusative case", "4 wrong out of 10.", True)
    item = build_plan(PlanInputs(review=NOTHING, grammar=pick)).items[0]
    assert (item.kind, item.pattern_key, item.done) == (
        PlanKind.GRAMMAR,
        PatternKey.ACCUSATIVE,
        True,
    )
    assert item.title == "Practise: Accusative case" and item.why == "4 wrong out of 10."


def test_homework_is_the_pending_exercises_oldest_first_plus_those_done_today() -> None:
    a, b, c = resource(1, "A"), resource(2, "B"), resource(3, "C")
    done = resource(2, "Done")
    plan = build_plan(
        PlanInputs(review=NOTHING, homework_pending=[a, b, c], homework_done_today=[done])
    )
    homework = [i for i in plan.items if i.kind == PlanKind.HOMEWORK]
    assert [(i.title, i.done) for i in homework] == [
        ("Workbook: A (S. 24)", False),
        ("Workbook: B (S. 24)", False),
        ("Workbook: Done (S. 24)", True),
    ]
    assert homework[0].why == "Chapter 1 workbook exercise you haven't marked done yet."
    assert homework[0].resource_id == a.id and homework[0].url == a.url


def test_writing_is_done_when_todays_checked_sentences_reach_the_target() -> None:
    task = TaskInfo(uuid.uuid4(), "5 sentences about your day", 5)

    def writing(sentences: int, t: TaskInfo | None = task) -> PlanItem:
        plan = build_plan(PlanInputs(review=NOTHING, writing_task=t, sentences_today=sentences))
        return next(i for i in plan.items if i.kind == PlanKind.WRITING)

    open_item = writing(2)
    assert open_item.done is False and open_item.task_id == task.id
    assert open_item.title == "Write: 5 sentences about your day"
    assert "You've checked 2 sentences today." in open_item.why
    assert writing(5).done is True
    free = writing(3, None)
    assert free.task_id is None and free.title == "Write 5 sentences" and free.done is False
    assert writing(5, None).done is True


def test_listening_uses_a_chapter_audio_when_there_is_one_and_tracks_it() -> None:
    audio = resource(3, "Dialog 2", "S. 30")
    pending = build_plan(PlanInputs(review=NOTHING, listening_pending=audio)).items
    item = next(i for i in pending if i.kind == PlanKind.LISTENING)
    assert (item.title, item.done, item.resource_id) == (
        "Listen: Dialog 2 (S. 30)",
        False,
        audio.id,
    )
    assert item.url == audio.url

    finished = build_plan(PlanInputs(review=NOTHING, listening_done_today=audio)).items
    assert next(i for i in finished if i.kind == PlanKind.LISTENING).done is True

    generic = build_plan(PlanInputs(review=NOTHING, current_chapter_number=4)).items
    item = next(i for i in generic if i.kind == PlanKind.LISTENING)
    assert item.title == "Listen to a dialogue from Chapter 4" and item.done is None


def test_speaking_names_the_words_and_says_where_they_came_from() -> None:
    def speaking(**kw: object) -> tuple[str, str, list[str]]:
        plan = build_plan(PlanInputs(review=NOTHING, **kw))  # type: ignore[arg-type]
        i = next(i for i in plan.items if i.kind == PlanKind.SPEAKING)
        return i.title, i.why, i.words

    title, why, words = speaking(
        speaking_words=["der Tisch", "gehen"], speaking_words_are_weak=True
    )
    assert title == "Say these aloud: der Tisch, gehen" and words == ["der Tisch", "gehen"]
    assert why.startswith("Words you got wrong most recently.")
    assert speaking(speaking_words=["die Lampe"])[1].startswith("Your newest words.")
    title, why, words = speaking()
    assert title == "Speak German aloud for 5 minutes" and words == []


# --- Streak and "am I on track?" -----------------------------------------------------------------

TODAY = date(2026, 11, 10)


def days_ago(*offsets: int) -> set[date]:
    return {TODAY - timedelta(days=n) for n in offsets}


def test_streak_counts_consecutive_days_and_survives_today_not_being_studied_yet() -> None:
    assert streak(days_ago(0, 1, 2), TODAY) == 3
    assert streak(days_ago(1, 2, 3), TODAY) == 3  # today isn't over: the streak is still alive
    assert streak(days_ago(2, 3), TODAY) == 0  # yesterday was missed: broken
    assert streak(days_ago(0, 2, 3), TODAY) == 1  # a gap ends the run
    assert streak(set(), TODAY) == 0


def test_the_week_strip_holds_the_days_studied_since_monday() -> None:
    # TODAY is Tuesday the 10th: the week began on Monday the 9th.
    days = days_ago(-1, 0, 1, 2)  # tomorrow, today, Monday, last Sunday
    assert week_studied(days, TODAY) == [date(2026, 11, 9), date(2026, 11, 10)]
    assert week_studied(set(), TODAY) == []


def test_a_learner_who_has_not_started_is_getting_started() -> None:
    p = assess(set(), TODAY, cards_due=0)
    assert p.status == TrackStatus.GETTING_STARTED and p.streak == 0 and p.last_studied is None


def test_studying_most_days_is_on_track() -> None:
    p = assess(days_ago(0, 1, 2, 4, 6), TODAY, cards_due=10)
    assert p.status == TrackStatus.ON_TRACK
    assert (p.streak, p.days_studied) == (3, 5)
    assert p.reason == "You studied on 5 of the last 7 days, 3 days in a row."


def test_a_new_learner_is_judged_on_the_days_they_have_had() -> None:
    p = assess(days_ago(0, 1), TODAY, cards_due=0)  # started yesterday, studied both days
    assert p.status == TrackStatus.ON_TRACK
    assert p.reason == "You studied on 2 of the last 2 days, 2 days in a row."


def test_two_missed_days_in_a_row_is_slipping() -> None:
    p = assess(days_ago(2, 3, 4, 5), TODAY, cards_due=0)
    assert p.status == TrackStatus.SLIPPING
    assert p.reason == "You last studied 2 days ago. A short session today gets you back."
    assert assess(days_ago(1), TODAY, 0).status != TrackStatus.SLIPPING  # one day off is fine


def test_a_pile_of_due_cards_is_slipping_even_if_you_studied_today() -> None:
    p = assess(days_ago(0, 1, 2, 3), TODAY, cards_due=BACKLOG_CARDS + 1)
    assert p.status == TrackStatus.SLIPPING and "cards are waiting" in p.reason


def test_studying_too_rarely_is_slipping_and_says_what_to_aim_for() -> None:
    p = assess(days_ago(0, 6), TODAY, cards_due=0)  # 2 of 7 days
    assert p.status == TrackStatus.SLIPPING
    assert p.reason == "You studied on 2 of the last 7 days. Aim for 4."


# --- Tasks from the class chat -----------------------------------------------------------------


def test_class_tasks_due_within_two_days_come_before_grammar_and_later_ones_after_homework() -> (
    None
):
    inputs = PlanInputs(
        review=ReviewInfo(due=12, new=0, retries_due=0, reviewed_today=0),
        grammar=GrammarPick(PatternKey.ACCUSATIVE, "Accusative", "4 wrong out of 10.", False),
        homework_pending=[resource()],
        class_tasks=[chat_task(5, "later"), chat_task(1, "soon"), chat_task(-3, "late")],
    )
    plan = build_plan(inputs)
    assert [(i.kind, i.title) for i in plan.items][:6] == [
        (PlanKind.REVIEW, "Review 12 cards"),
        (PlanKind.CLASS_TASK, "late"),
        (PlanKind.CLASS_TASK, "soon"),
        (PlanKind.GRAMMAR, "Practise: Accusative"),
        (PlanKind.HOMEWORK, "Workbook: Übung (S. 24)"),
        (PlanKind.CLASS_TASK, "later"),
    ]


def test_a_class_task_says_how_soon_it_is_due() -> None:
    def why(days_left: int) -> str:
        plan = build_plan(PlanInputs(review=NOTHING, class_tasks=[chat_task(days_left)]))
        return next(i.why for i in plan.items if i.kind == PlanKind.CLASS_TASK)

    assert why(-3) == "From your class chat: 3 days overdue."
    assert why(-1) == "From your class chat: due yesterday."
    assert why(0) == "From your class chat: due today."
    assert why(1) == "From your class chat: due tomorrow."
    assert why(2) == "From your class chat: due in 2 days."
    assert why(6) == "From your class chat: due in 6 days."


def test_tasks_more_than_a_week_away_are_left_off_and_the_list_is_capped() -> None:
    days = [-1, 0, 1, 2, 3, 4, 5, 6, 8, 30]  # 4 urgent, 4 later, 2 too far
    plan = build_plan(PlanInputs(review=NOTHING, class_tasks=[chat_task(n, f"d{n}") for n in days]))
    titles = [i.title for i in plan.items if i.kind == PlanKind.CLASS_TASK]
    assert titles == ["d-1", "d0", "d1", "d3", "d4"]  # 3 urgent, 2 later, nothing past 7 days


def test_a_task_ticked_off_today_stays_in_the_plan_as_done() -> None:
    items = build_plan(
        PlanInputs(review=NOTHING, class_tasks=[chat_task(0, "done", done_today=True)])
    ).items
    (item,) = [i for i in items if i.kind == PlanKind.CLASS_TASK]
    assert item.done is True and item.id.startswith("class_task:")


def test_the_plan_with_class_tasks_still_fits_in_an_hour() -> None:
    plan = build_plan(
        PlanInputs(
            review=ReviewInfo(due=100, new=10, retries_due=0, reviewed_today=0),
            grammar=GrammarPick(PatternKey.ACCUSATIVE, "Accusative", "4 wrong out of 10.", False),
            homework_pending=[resource(), resource()],
            class_tasks=[chat_task(n) for n in range(6)],
        )
    )
    assert plan.total_minutes <= 60 and plan.note and "Left for another day" in plan.note
