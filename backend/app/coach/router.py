from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select

from app.ai.deps import GatewayDep
from app.coach import service
from app.coach.deps import LanguageToolDep
from app.coach.merge import Label, Source
from app.coach.models import CoachCheck, CoachCorrection, CorrectionStatus, Decision, WritingTask
from app.coach.schemas import (
    VERIFY_WARNING,
    CheckIn,
    CheckOut,
    CorrectionOut,
    TaskIn,
    TaskOut,
)
from app.core.auth import CurrentUserDep
from app.core.config import get_settings
from app.core.database import SessionDep
from app.grammar.catalog import PATTERNS

router = APIRouter(prefix="/coach", tags=["coach"])


def _correction_out(c: CoachCorrection) -> CorrectionOut:
    return CorrectionOut(
        id=c.id,
        start=c.start,
        end=c.end,
        wrong=c.wrong,
        correct=c.correct,
        sentence_wrong=c.sentence_wrong,
        sentence_correct=c.sentence_correct,
        label=c.label,
        warning=VERIFY_WARNING if c.label == Label.UNCERTAIN else None,
        sources=[Source(x) for x in c.sources],
        pattern_key=c.pattern_key,
        pattern_title=PATTERNS[c.pattern_key].title if c.pattern_key else None,
        category=c.category,
        explanation=c.explanation,
        alternatives=c.alternatives,
        status=c.status,
        mistake_id=c.mistake_id,
    )


def _build_check_out(
    check: CoachCheck, corrections: list[CoachCorrection], task: WritingTask | None
) -> CheckOut:
    task_done = None
    if check.task_id:
        task_done = task is not None and check.sentence_count >= task.min_sentences
    return CheckOut(
        id=check.id,
        task_id=check.task_id,
        text=check.text,
        redacted=check.redacted,
        suggested_text=check.suggested_text,
        sentence_count=check.sentence_count,
        corrections=[_correction_out(c) for c in corrections],
        explanation=check.explanation,
        practice=check.practice,
        practice_source=check.practice_source,
        checked_by=check.checked_by,
        ai_status=check.ai_status,
        ai_message=check.ai_message,
        task_done=task_done,
        created_at=check.created_at,
    )


async def _check_out(
    session: SessionDep, check: CoachCheck, corrections: list[CoachCorrection]
) -> CheckOut:
    task = await session.get(WritingTask, check.task_id) if check.task_id else None
    return _build_check_out(check, corrections, task)


async def _corrections(session: SessionDep, check_id: UUID) -> list[CoachCorrection]:
    rows = await session.scalars(
        select(CoachCorrection)
        .where(CoachCorrection.check_id == check_id)
        .order_by(CoachCorrection.start, CoachCorrection.end)
    )
    return list(rows)


async def _owned_task(session: SessionDep, user_id: UUID, task_id: UUID) -> WritingTask:
    task = await session.scalar(
        select(WritingTask).where(WritingTask.id == task_id, WritingTask.user_id == user_id)
    )
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Writing task not found")
    return task


@router.post("/check", status_code=status.HTTP_201_CREATED)
async def check_writing(
    body: CheckIn,
    user: CurrentUserDep,
    session: SessionDep,
    gateway: GatewayDep,
    languagetool: LanguageToolDep,
) -> CheckOut:
    """Checks German writing: LanguageTool and our A1 rules find and verify mistakes, the AI
    explains and adds practice. Each correction says how sure we are. Nothing is added to the
    mistake log until the learner accepts a correction."""
    task = await _owned_task(session, user.id, body.task_id) if body.task_id else None
    check, corrections = await service.run_check(
        session,
        gateway,
        languagetool,
        user.id,
        body.text,
        task,
        redact_names=get_settings().redact_names,
    )
    return await _check_out(session, check, corrections)


@router.get("/checks")
async def list_checks(
    user: CurrentUserDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[CheckOut]:
    """Recent checks, newest first."""
    checks = list(
        await session.scalars(
            select(CoachCheck)
            .where(CoachCheck.user_id == user.id)
            .order_by(CoachCheck.created_at.desc(), CoachCheck.id)
            .limit(limit)
        )
    )
    # Three queries however many checks there are: the checks, all their corrections, their tasks.
    by_check: dict[UUID, list[CoachCorrection]] = {c.id: [] for c in checks}
    if checks:
        for correction in await session.scalars(
            select(CoachCorrection)
            .where(CoachCorrection.check_id.in_(by_check))
            .order_by(CoachCorrection.start, CoachCorrection.end)
        ):
            by_check[correction.check_id].append(correction)
    task_ids = {c.task_id for c in checks if c.task_id}
    tasks: dict[UUID, WritingTask] = {}
    if task_ids:
        rows = await session.scalars(select(WritingTask).where(WritingTask.id.in_(task_ids)))
        tasks = {t.id: t for t in rows}
    return [
        _build_check_out(c, by_check[c.id], tasks.get(c.task_id) if c.task_id else None)
        for c in checks
    ]


@router.get("/checks/{check_id}")
async def get_check(check_id: UUID, user: CurrentUserDep, session: SessionDep) -> CheckOut:
    check = await session.scalar(
        select(CoachCheck).where(CoachCheck.id == check_id, CoachCheck.user_id == user.id)
    )
    if check is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Check not found")
    return await _check_out(session, check, await _corrections(session, check.id))


@router.post("/corrections/{correction_id}/{decision}")
async def decide_correction(
    correction_id: UUID, decision: Decision, user: CurrentUserDep, session: SessionDep
) -> CorrectionOut:
    """Accept (adds it to the mistake log and gives it a retry card), reject, or flag a
    correction. Flag means: I think this is wrong, or I'll ask my teacher."""
    correction = await session.scalar(
        select(CoachCorrection).where(
            CoachCorrection.id == correction_id, CoachCorrection.user_id == user.id
        )
    )
    if correction is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Correction not found")
    try:
        await service.decide(session, user.id, correction, decision)
    except service.DecisionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return _correction_out(correction)


@router.get("/flagged")
async def flagged(user: CurrentUserDep, session: SessionDep) -> list[CorrectionOut]:
    """Corrections the learner flagged, to bring to the teacher. Newest first."""
    rows = await session.scalars(
        select(CoachCorrection)
        .where(
            CoachCorrection.user_id == user.id,
            CoachCorrection.status == CorrectionStatus.FLAGGED,
        )
        .order_by(CoachCorrection.created_at.desc(), CoachCorrection.id)
    )
    return [_correction_out(c) for c in rows]


# --- Writing tasks ---


async def _task_out(session: SessionDep, user_id: UUID, tasks: list[WritingTask]) -> list[TaskOut]:
    progress = await service.task_progress(session, user_id, tasks)
    return [
        TaskOut(
            id=t.id,
            prompt=t.prompt,
            min_sentences=t.min_sentences,
            done=progress[t.id][1],
            checks=progress[t.id][0],
            created_at=t.created_at,
        )
        for t in tasks
    ]


@router.get("/tasks")
async def list_tasks(user: CurrentUserDep, session: SessionDep) -> list[TaskOut]:
    tasks = list(
        await session.scalars(
            select(WritingTask)
            .where(WritingTask.user_id == user.id)
            .order_by(WritingTask.created_at.desc(), WritingTask.id)
        )
    )
    return await _task_out(session, user.id, tasks)


@router.post("/tasks", status_code=status.HTTP_201_CREATED)
async def create_task(body: TaskIn, user: CurrentUserDep, session: SessionDep) -> TaskOut:
    """A writing task such as "5 sentences about your day". Submit writing for it with
    POST /coach/check and its task_id."""
    task = WritingTask(user_id=user.id, prompt=body.prompt, min_sentences=body.min_sentences)
    session.add(task)
    await session.commit()
    return (await _task_out(session, user.id, [task]))[0]


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: UUID, user: CurrentUserDep, session: SessionDep) -> Response:
    """Deletes the task. Its checks stay, without the task."""
    await session.delete(await _owned_task(session, user.id, task_id))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
