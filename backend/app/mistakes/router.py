from datetime import timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select

from app.core.auth import CurrentUserDep
from app.core.database import SessionDep
from app.course.models import Chapter
from app.grammar.catalog import PATTERNS, MistakeCategory, PatternKey
from app.mistakes.models import Mistake, mistake_words
from app.mistakes.schemas import (
    CategoryCount,
    MistakeCreate,
    MistakeOut,
    MistakeSummaryOut,
    MistakeUpdate,
    PatternCount,
    check_versions_differ,
)
from app.mistakes.service import find_repeat, log_mistake, match_key, mistakes_out, sync_evidence
from app.review import service as review_service
from app.vocabulary.models import VocabWord

router = APIRouter(tags=["mistakes"])

_REQUIRED_FIELDS = {"wrong", "correct", "category", "word_ids"}


def _unprocessable(detail: Any) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail)


async def _check_chapter(session: SessionDep, user_id: UUID, chapter_id: UUID | None) -> None:
    if chapter_id is None:
        return
    owned = await session.scalar(
        select(Chapter.id).where(Chapter.id == chapter_id, Chapter.user_id == user_id)
    )
    if owned is None:
        raise _unprocessable("Unknown chapter")


async def _owned_words(session: SessionDep, user_id: UUID, word_ids: list[UUID]) -> list[VocabWord]:
    wanted = set(word_ids)
    if not wanted:
        return []
    words = list(
        await session.scalars(
            select(VocabWord).where(VocabWord.id.in_(wanted), VocabWord.user_id == user_id)
        )
    )
    if len(words) != len(wanted):
        raise _unprocessable("Unknown word")
    return words


async def _get_mistake(session: SessionDep, user_id: UUID, mistake_id: UUID) -> Mistake:
    mistake = await session.scalar(
        select(Mistake).where(Mistake.id == mistake_id, Mistake.user_id == user_id)
    )
    if mistake is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mistake not found")
    return mistake


async def _one_out(session: SessionDep, mistake: Mistake) -> MistakeOut:
    return (await mistakes_out(session, [mistake]))[0]


@router.get("/mistakes")
async def list_mistakes(
    user: CurrentUserDep,
    session: SessionDep,
    category: MistakeCategory | None = None,
    pattern_key: PatternKey | None = None,
    chapter_id: UUID | None = None,
    word_id: UUID | None = None,
    repeats_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[MistakeOut]:
    """The mistake log, newest first."""
    query = select(Mistake).where(Mistake.user_id == user.id)
    if category is not None:
        query = query.where(Mistake.category == category)
    if pattern_key is not None:
        query = query.where(Mistake.pattern_key == pattern_key)
    if chapter_id is not None:
        query = query.where(Mistake.chapter_id == chapter_id)
    if word_id is not None:
        with_word = select(mistake_words.c.mistake_id).where(mistake_words.c.word_id == word_id)
        query = query.where(Mistake.id.in_(with_word))
    if repeats_only:
        query = query.where(Mistake.repeat_of_id.is_not(None))
    mistakes = await session.scalars(
        query.order_by(Mistake.created_at.desc(), Mistake.id).limit(limit)
    )
    return await mistakes_out(session, list(mistakes))


@router.get("/mistakes/summary")
async def mistake_summary(user: CurrentUserDep, session: SessionDep) -> MistakeSummaryOut:
    """Mistakes grouped by category and by grammar pattern, most frequent first."""
    recent = Mistake.created_at >= review_service.utcnow() - timedelta(days=30)
    counts = (
        func.count(),
        func.count().filter(recent),
        func.count(Mistake.repeat_of_id),
    )
    mine = Mistake.user_id == user.id
    by_category = [
        CategoryCount(category=c, total=t, last_30_days=r, repeats=rep)
        for c, t, r, rep in await session.execute(
            select(Mistake.category, *counts).where(mine).group_by(Mistake.category)
        )
    ]
    by_pattern = [
        PatternCount(key=k, title=PATTERNS[k].title, total=t, last_30_days=r, repeats=rep)
        for k, t, r, rep in await session.execute(
            select(Mistake.pattern_key, *counts)
            .where(mine, Mistake.pattern_key.is_not(None))
            .group_by(Mistake.pattern_key)
        )
        if k is not None
    ]
    by_category.sort(key=lambda c: (-c.last_30_days, -c.total, c.category))
    by_pattern.sort(key=lambda p: (-p.last_30_days, -p.total, p.key))
    return MistakeSummaryOut(
        total=sum(c.total for c in by_category),
        last_30_days=sum(c.last_30_days for c in by_category),
        repeats=sum(c.repeats for c in by_category),
        by_category=by_category,
        by_pattern=by_pattern,
    )


@router.post("/mistakes", status_code=status.HTTP_201_CREATED)
async def create_mistake(
    body: MistakeCreate, user: CurrentUserDep, session: SessionDep
) -> MistakeOut:
    """Logs a mistake. It is checked for repeats and becomes an error-retry review card."""
    await _check_chapter(session, user.id, body.chapter_id)
    assert body.category is not None  # filled in by the schema
    mistake = await log_mistake(
        session,
        user.id,
        wrong=body.wrong,
        correct=body.correct,
        category=body.category,
        pattern_key=body.pattern_key,
        explanation=body.explanation,
        chapter_id=body.chapter_id,
        source=body.source,
        words=await _owned_words(session, user.id, body.word_ids),
    )
    await session.commit()
    return await _one_out(session, mistake)


@router.get("/mistakes/{mistake_id}")
async def get_mistake(mistake_id: UUID, user: CurrentUserDep, session: SessionDep) -> MistakeOut:
    return await _one_out(session, await _get_mistake(session, user.id, mistake_id))


@router.patch("/mistakes/{mistake_id}")
async def update_mistake(
    mistake_id: UUID, body: MistakeUpdate, user: CurrentUserDep, session: SessionDep
) -> MistakeOut:
    mistake = await _get_mistake(session, user.id, mistake_id)
    changes = body.model_dump(exclude_unset=True)
    nulled = sorted(k for k in _REQUIRED_FIELDS if k in changes and changes[k] is None)
    if nulled:
        raise _unprocessable(f"These fields can't be null: {nulled}")
    try:
        check_versions_differ(
            changes.get("wrong", mistake.wrong), changes.get("correct", mistake.correct)
        )
    except ValueError as exc:
        raise _unprocessable(str(exc)) from exc

    if "chapter_id" in changes:
        await _check_chapter(session, user.id, changes["chapter_id"])
    if "word_ids" in changes:
        mistake.words = await _owned_words(session, user.id, changes.pop("word_ids"))
    for field, value in changes.items():
        setattr(mistake, field, value)
    mistake.match_key = match_key(mistake.correct)
    await session.flush()
    mistake.repeat_of_id = await find_repeat(session, mistake, new=False)
    await sync_evidence(session, mistake)
    await session.commit()
    return await _one_out(session, mistake)


@router.delete("/mistakes/{mistake_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mistake(mistake_id: UUID, user: CurrentUserDep, session: SessionDep) -> Response:
    """Deletes the mistake with its retry card and its grammar evidence."""
    mistake = await _get_mistake(session, user.id, mistake_id)
    await session.delete(mistake)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
