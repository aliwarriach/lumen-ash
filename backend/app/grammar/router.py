from collections import defaultdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import delete, select

from app.core.auth import CurrentUserDep
from app.core.database import SessionDep
from app.course.models import Chapter
from app.grammar.catalog import PATTERNS, Pattern, PatternKey
from app.grammar.exercises import BOOK_CHAPTER, BY_ID, EXERCISES, Exercise, is_correct
from app.grammar.models import GrammarChapterLink
from app.grammar.schemas import (
    CommonMistakeOut,
    ExampleOut,
    ExerciseOut,
    PatternChaptersIn,
    PatternOut,
    PatternStatsOut,
    PatternSummaryOut,
    PracticeAnswerIn,
    PracticeAnswerOut,
    PracticeOut,
    PracticeSetOut,
    WeakPatternOut,
)
from app.grammar.service import add_evidence, pattern_stats, recent_evidence, weak_patterns
from app.review import service as review_service

router = APIRouter(tags=["grammar"])


async def _chapter_links(session: SessionDep, user_id: UUID) -> dict[PatternKey, list[UUID]]:
    links: dict[PatternKey, list[UUID]] = defaultdict(list)
    rows = await session.execute(
        select(GrammarChapterLink.pattern_key, GrammarChapterLink.chapter_id)
        .join(Chapter, Chapter.id == GrammarChapterLink.chapter_id)
        .where(GrammarChapterLink.user_id == user_id)
        .order_by(Chapter.number)
    )
    for key, chapter_id in rows:
        links[key].append(chapter_id)
    return links


def _summary(p: Pattern, chapter_ids: list[UUID], stats: PatternStatsOut) -> PatternSummaryOut:
    return PatternSummaryOut(
        key=p.key,
        title=p.title,
        category=p.category,
        chapter_ids=chapter_ids,
        book_chapter=BOOK_CHAPTER[p.key],
        exercise_count=len(EXERCISES[p.key]),
        stats=stats,
    )


@router.get("/grammar/patterns")
async def list_patterns(
    user: CurrentUserDep, session: SessionDep, chapter_id: UUID | None = None
) -> list[PatternSummaryOut]:
    """Every A1 pattern with the learner's accuracy, in course order."""
    links = await _chapter_links(session, user.id)
    stats = await pattern_stats(session, user.id, review_service.utcnow())
    return [
        _summary(p, links[p.key], stats[p.key])
        for p in sorted(PATTERNS.values(), key=lambda p: BOOK_CHAPTER[p.key])
        if chapter_id is None or chapter_id in links[p.key]
    ]


@router.get("/grammar/weak")
async def list_weak_patterns(
    user: CurrentUserDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> list[WeakPatternOut]:
    """The learner's weakest patterns right now, each with the reason and recent wrong answers."""
    return await weak_patterns(session, user.id, review_service.utcnow(), limit)


async def _pattern_out(session: SessionDep, user_id: UUID, key: PatternKey) -> PatternOut:
    p = PATTERNS[key]
    links = await _chapter_links(session, user_id)
    stats = await pattern_stats(session, user_id, review_service.utcnow())
    return PatternOut(
        **_summary(p, links[key], stats[key]).model_dump(),
        explanation=p.explanation,
        examples=[ExampleOut(german=e.german, english=e.english) for e in p.examples],
        common_mistakes=[
            CommonMistakeOut(wrong=m.wrong, correct=m.correct, why=m.why) for m in p.common_mistakes
        ],
        practice=[PracticeOut(prompt=x.prompt, answer=x.answer) for x in p.practice],
        evidence=await recent_evidence(session, user_id, key),
    )


@router.get("/grammar/patterns/{key}")
async def get_pattern(key: PatternKey, user: CurrentUserDep, session: SessionDep) -> PatternOut:
    return await _pattern_out(session, user.id, key)


@router.put("/grammar/patterns/{key}/chapters")
async def set_pattern_chapters(
    key: PatternKey, body: PatternChaptersIn, user: CurrentUserDep, session: SessionDep
) -> PatternOut:
    """Sets which of the learner's chapters cover this pattern (replaces the previous list)."""
    wanted = set(body.chapter_ids)
    owned = set(
        await session.scalars(
            select(Chapter.id).where(Chapter.id.in_(wanted), Chapter.user_id == user.id)
        )
    )
    if owned != wanted:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown chapter")
    await session.execute(
        delete(GrammarChapterLink).where(
            GrammarChapterLink.user_id == user.id, GrammarChapterLink.pattern_key == key
        )
    )
    session.add_all(
        GrammarChapterLink(user_id=user.id, pattern_key=key, chapter_id=cid) for cid in wanted
    )
    await session.commit()
    return await _pattern_out(session, user.id, key)


def _exercise_out(ex: Exercise) -> ExerciseOut:
    return ExerciseOut(
        id=ex.id,
        kind=ex.kind,
        prompt=ex.prompt,
        english=ex.english,
        options=list(ex.options),
        tiles=list(ex.tiles),
        answers=list(ex.answers),
        exact_case=ex.exact_case,
        end=ex.end,
        hint=ex.hint,
        why=ex.why,
    )


@router.get("/grammar/patterns/{key}/practice")
async def get_practice(key: PatternKey, user: CurrentUserDep) -> PracticeSetOut:
    """The practice exercises for one pattern. The same for everyone; no AI is involved."""
    return PracticeSetOut(
        key=key,
        title=PATTERNS[key].title,
        book_chapter=BOOK_CHAPTER[key],
        exercises=[_exercise_out(ex) for ex in EXERCISES[key]],
    )


@router.post("/grammar/practice/answers")
async def answer_practice(
    body: PracticeAnswerIn, user: CurrentUserDep, session: SessionDep
) -> PracticeAnswerOut:
    """Checks one practice answer and counts it towards the pattern's accuracy. The app checks
    it too, for instant feedback; this result is the one that is stored."""
    found = BY_ID.get(body.exercise_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown exercise")
    key, exercise = found
    correct = is_correct(exercise, body.given)
    add_evidence(
        session,
        user.id,
        {key: correct},
        review_service.utcnow(),
        exercise_id=exercise.id,
        given=body.given.strip()[:300],
    )
    await session.commit()
    return PracticeAnswerOut(correct=correct, expected=exercise.answers[0], pattern_key=key)
