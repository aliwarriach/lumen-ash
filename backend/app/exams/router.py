from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select

from app.core.auth import CurrentUserDep
from app.core.database import SessionDep
from app.course.models import Chapter
from app.exams import service
from app.exams.models import Exam, ExamResult
from app.exams.schemas import (
    ExamCreate,
    ExamDetailOut,
    ExamOut,
    ExamUpdate,
    ResultCreate,
    ResultOut,
)
from app.review import service as review_service
from app.review.router import TimezoneDep

router = APIRouter(tags=["exams"])

_REQUIRED_FIELDS = {"kind", "title", "exam_date", "target_percent"}


def _unprocessable(detail: Any) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail)


async def _owned_chapters(session: SessionDep, user_id: UUID, ids: list[UUID]) -> list[Chapter]:
    wanted = set(ids)
    if not wanted:
        return []
    chapters = list(
        await session.scalars(
            select(Chapter)
            .where(Chapter.id.in_(wanted), Chapter.user_id == user_id)
            .order_by(Chapter.number)
        )
    )
    if len(chapters) != len(wanted):
        raise _unprocessable("Unknown chapter")
    return chapters


async def _get_exam(session: SessionDep, user_id: UUID, exam_id: UUID) -> Exam:
    exam = await session.scalar(select(Exam).where(Exam.id == exam_id, Exam.user_id == user_id))
    if exam is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Test not found")
    return exam


async def _detail(session: SessionDep, user_id: UUID, exam: Exam, tz: TimezoneDep) -> ExamDetailOut:
    return await service.exam_detail(session, user_id, exam, review_service.utcnow(), tz)


# --- Tests ---


@router.get("/exams")
async def list_exams(user: CurrentUserDep, session: SessionDep, tz: TimezoneDep) -> list[ExamOut]:
    """Upcoming tests first (soonest first), then past ones (latest first)."""
    now = review_service.utcnow()
    today = service.local_today(now, tz)
    exams = list(await session.scalars(select(Exam).where(Exam.user_id == user.id)))
    exams.sort(key=lambda e: (e.exam_date < today, abs((e.exam_date - today).days)))
    return [await service.exam_out(session, user.id, e, now, tz) for e in exams]


@router.post("/exams", status_code=status.HTTP_201_CREATED)
async def create_exam(
    body: ExamCreate, user: CurrentUserDep, session: SessionDep, tz: TimezoneDep
) -> ExamDetailOut:
    """Adds a test to prepare for. With no chapters it covers the whole course."""
    exam = Exam(
        user_id=user.id,
        kind=body.kind,
        title=body.title,
        exam_date=body.exam_date,
        whole_course=not body.chapter_ids,
        target_percent=body.target_percent,
        notes=body.notes,
        chapters=await _owned_chapters(session, user.id, body.chapter_ids),
    )
    session.add(exam)
    await session.commit()
    return await _detail(session, user.id, exam, tz)


@router.get("/exams/{exam_id}")
async def get_exam(
    exam_id: UUID, user: CurrentUserDep, session: SessionDep, tz: TimezoneDep
) -> ExamDetailOut:
    """Countdown, readiness (by chapter and skill, with the gaps and why), the revision plan and
    the results entered for this test."""
    return await _detail(session, user.id, await _get_exam(session, user.id, exam_id), tz)


@router.patch("/exams/{exam_id}")
async def update_exam(
    exam_id: UUID, body: ExamUpdate, user: CurrentUserDep, session: SessionDep, tz: TimezoneDep
) -> ExamDetailOut:
    exam = await _get_exam(session, user.id, exam_id)
    changes = body.model_dump(exclude_unset=True)
    nulled = sorted(k for k in _REQUIRED_FIELDS if k in changes and changes[k] is None)
    if nulled:
        raise _unprocessable(f"These fields can't be null: {nulled}")
    if "chapter_ids" in changes:
        ids = changes.pop("chapter_ids") or []
        exam.chapters = await _owned_chapters(session, user.id, ids)
        exam.whole_course = not ids
    for field, value in changes.items():
        setattr(exam, field, value)
    await session.commit()
    return await _detail(session, user.id, exam, tz)


@router.delete("/exams/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exam(exam_id: UUID, user: CurrentUserDep, session: SessionDep) -> Response:
    """Deletes the test. Results entered for it are kept, no longer tied to a test."""
    await session.delete(await _get_exam(session, user.id, exam_id))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Results ---


async def _titles(session: SessionDep, user_id: UUID) -> dict[UUID, str]:
    rows = await session.execute(select(Exam.id, Exam.title).where(Exam.user_id == user_id))
    return {i: t for i, t in rows}


@router.post("/exam-results", status_code=status.HTTP_201_CREATED)
async def create_result(body: ResultCreate, user: CurrentUserDep, session: SessionDep) -> ResultOut:
    """Records a practice test or the real result. Chapters you lost marks on count as weak
    areas in readiness."""
    exam = await _get_exam(session, user.id, body.exam_id) if body.exam_id else None
    result = ExamResult(
        user_id=user.id,
        exam_id=exam.id if exam else None,
        kind=body.kind,
        title=body.title,
        taken_on=body.taken_on,
        score=body.score,
        max_score=body.max_score,
        sections=[s.model_dump(mode="json") for s in body.sections],
        notes=body.notes,
        weak_chapters=await _owned_chapters(session, user.id, body.weak_chapter_ids),
    )
    session.add(result)
    await session.commit()
    return service.result_out(result, exam.title if exam else None)


@router.get("/exam-results")
async def list_results(
    user: CurrentUserDep,
    session: SessionDep,
    exam_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[ResultOut]:
    """Entered results, newest first."""
    query = select(ExamResult).where(ExamResult.user_id == user.id)
    if exam_id is not None:
        query = query.where(ExamResult.exam_id == exam_id)
    results = await session.scalars(
        query.order_by(ExamResult.taken_on.desc(), ExamResult.created_at.desc()).limit(limit)
    )
    titles = await _titles(session, user.id)
    return [service.result_out(r, titles.get(r.exam_id) if r.exam_id else None) for r in results]


@router.delete("/exam-results/{result_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_result(result_id: UUID, user: CurrentUserDep, session: SessionDep) -> Response:
    result = await session.scalar(
        select(ExamResult).where(ExamResult.id == result_id, ExamResult.user_id == user.id)
    )
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Result not found")
    await session.delete(result)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
