from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.core.auth import CurrentUserDep
from app.core.database import SessionDep
from app.course.import_links import seed_new_learner
from app.course.models import Chapter, ChapterResource
from app.course.schemas import (
    ChapterCreate,
    ChapterOut,
    ChapterProgress,
    ChapterStatus,
    ChapterSummaryOut,
    ChapterUpdate,
    ResourceCreate,
    ResourceOut,
    ResourceUpdate,
    WordCounts,
)
from app.vocabulary.models import VocabWord, WordStage

router = APIRouter(tags=["course"])

# Fields that may not be cleared with an explicit null in a PATCH.
_REQUIRED_CHAPTER_FIELDS = {"number", "title", "topics"}
_REQUIRED_RESOURCE_FIELDS = {"kind", "title", "completed"}


def _patch_fields(update: ChapterUpdate | ResourceUpdate, required: set[str]) -> dict[str, Any]:
    fields = update.model_dump(exclude_unset=True)
    nulled = sorted(k for k in required if k in fields and fields[k] is None)
    if nulled:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"These fields can't be null: {nulled}"
        )
    if "url" in fields and fields["url"] is not None:
        fields["url"] = str(fields["url"])
    return fields


def _progress(total: int, completed: int) -> ChapterProgress:
    if total == 0 or completed == 0:
        state = ChapterStatus.NOT_STARTED
    elif completed < total:
        state = ChapterStatus.IN_PROGRESS
    else:
        state = ChapterStatus.COMPLETED
    return ChapterProgress(total=total, completed=completed, status=state)


async def _word_counts(
    session: SessionDep, user_id: UUID, chapter_ids: list[UUID]
) -> dict[UUID, WordCounts]:
    if not chapter_ids:
        return {}
    rows = await session.execute(
        select(
            VocabWord.chapter_id,
            func.count(),
            func.count().filter(VocabWord.stage == WordStage.MASTERED),
        )
        .where(VocabWord.user_id == user_id, VocabWord.chapter_id.in_(chapter_ids))
        .group_by(VocabWord.chapter_id)
    )
    return {cid: WordCounts(total=t, mastered=m) for cid, t, m in rows if cid is not None}


async def _chapter_out(session: SessionDep, chapter: Chapter) -> ChapterOut:
    done = sum(1 for r in chapter.resources if r.completed_at is not None)
    counts = await _word_counts(session, chapter.user_id, [chapter.id])
    return ChapterOut(
        id=chapter.id,
        number=chapter.number,
        title=chapter.title,
        topics=chapter.topics,
        notes=chapter.notes,
        progress=_progress(len(chapter.resources), done),
        words=counts.get(chapter.id, WordCounts()),
        resources=[ResourceOut.model_validate(r) for r in chapter.resources],
    )


def _number_taken() -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, "You already have a chapter with this number")


async def _get_chapter(session: SessionDep, user_id: UUID, chapter_id: UUID) -> Chapter:
    chapter = await session.scalar(
        select(Chapter)
        .where(Chapter.id == chapter_id, Chapter.user_id == user_id)
        .options(selectinload(Chapter.resources))
        .execution_options(populate_existing=True)
    )
    if chapter is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chapter not found")
    return chapter


async def _get_resource(session: SessionDep, user_id: UUID, resource_id: UUID) -> ChapterResource:
    resource = await session.scalar(
        select(ChapterResource).where(
            ChapterResource.id == resource_id, ChapterResource.user_id == user_id
        )
    )
    if resource is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resource not found")
    return resource


# --- Chapters ---


@router.get("/chapters")
async def list_chapters(user: CurrentUserDep, session: SessionDep) -> list[ChapterSummaryOut]:
    """The course map: every chapter with its progress."""
    await seed_new_learner(session, user.id)  # a brand-new account starts with the course
    rows = await session.execute(
        select(
            Chapter,
            func.count(ChapterResource.id),
            func.count(ChapterResource.completed_at),
        )
        .outerjoin(ChapterResource, ChapterResource.chapter_id == Chapter.id)
        .where(Chapter.user_id == user.id)
        .group_by(Chapter.id)
        .order_by(Chapter.number)
    )
    chapters = rows.all()
    counts = await _word_counts(session, user.id, [c.id for c, _, _ in chapters])
    return [
        ChapterSummaryOut(
            id=chapter.id,
            number=chapter.number,
            title=chapter.title,
            topics=chapter.topics,
            progress=_progress(total, completed),
            words=counts.get(chapter.id, WordCounts()),
        )
        for chapter, total, completed in chapters
    ]


@router.post("/chapters", status_code=status.HTTP_201_CREATED)
async def create_chapter(
    body: ChapterCreate, user: CurrentUserDep, session: SessionDep
) -> ChapterOut:
    chapter = Chapter(user_id=user.id, **body.model_dump())
    session.add(chapter)
    try:
        await session.commit()
    except IntegrityError as exc:
        raise _number_taken() from exc
    return await _chapter_out(session, await _get_chapter(session, user.id, chapter.id))


@router.get("/chapters/{chapter_id}")
async def get_chapter(chapter_id: UUID, user: CurrentUserDep, session: SessionDep) -> ChapterOut:
    return await _chapter_out(session, await _get_chapter(session, user.id, chapter_id))


@router.patch("/chapters/{chapter_id}")
async def update_chapter(
    chapter_id: UUID, body: ChapterUpdate, user: CurrentUserDep, session: SessionDep
) -> ChapterOut:
    chapter = await _get_chapter(session, user.id, chapter_id)
    for field, value in _patch_fields(body, _REQUIRED_CHAPTER_FIELDS).items():
        setattr(chapter, field, value)
    try:
        await session.commit()
    except IntegrityError as exc:
        raise _number_taken() from exc
    return await _chapter_out(session, await _get_chapter(session, user.id, chapter_id))


@router.delete("/chapters/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chapter(chapter_id: UUID, user: CurrentUserDep, session: SessionDep) -> Response:
    chapter = await _get_chapter(session, user.id, chapter_id)
    await session.delete(chapter)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Resources ---


@router.post("/chapters/{chapter_id}/resources", status_code=status.HTTP_201_CREATED)
async def create_resource(
    chapter_id: UUID, body: ResourceCreate, user: CurrentUserDep, session: SessionDep
) -> ResourceOut:
    chapter = await _get_chapter(session, user.id, chapter_id)
    next_position = max((r.position for r in chapter.resources), default=-1) + 1
    resource = ChapterResource(
        user_id=user.id,
        chapter_id=chapter.id,
        kind=body.kind,
        title=body.title,
        reference=body.reference,
        url=str(body.url) if body.url else None,
        position=next_position,
    )
    session.add(resource)
    await session.commit()
    return ResourceOut.model_validate(resource)


@router.patch("/resources/{resource_id}")
async def update_resource(
    resource_id: UUID, body: ResourceUpdate, user: CurrentUserDep, session: SessionDep
) -> ResourceOut:
    resource = await _get_resource(session, user.id, resource_id)
    fields = _patch_fields(body, _REQUIRED_RESOURCE_FIELDS)
    completed = fields.pop("completed", None)
    for field, value in fields.items():
        setattr(resource, field, value)
    if completed is True and resource.completed_at is None:
        resource.completed_at = datetime.now(UTC)
    elif completed is False:
        resource.completed_at = None
    await session.commit()
    await session.refresh(resource)
    return ResourceOut.model_validate(resource)


@router.delete("/resources/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resource(resource_id: UUID, user: CurrentUserDep, session: SessionDep) -> Response:
    resource = await _get_resource(session, user.id, resource_id)
    await session.delete(resource)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
