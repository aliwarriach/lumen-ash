from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select

from app.ai.deps import GatewayDep
from app.capture import service
from app.capture.models import ClassTask
from app.capture.schemas import ClassTaskBatchIn, ClassTaskOut, ClassTaskUpdate, ScanIn, ScanOut
from app.core.auth import CurrentUserDep
from app.core.database import SessionDep
from app.exams.service import local_today
from app.review import service as review_service
from app.review.router import TimezoneDep

router = APIRouter(tags=["capture"])

DONE_VISIBLE = timedelta(days=14)  # finished tasks stay listed for two weeks

_NOT_NULL = {"kind", "title"}


async def _get_task(session: SessionDep, user_id: UUID, task_id: UUID) -> ClassTask:
    task = await session.scalar(
        select(ClassTask).where(ClassTask.id == task_id, ClassTask.user_id == user_id)
    )
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return task


@router.post("/capture/scan")
async def scan(
    body: ScanIn,
    user: CurrentUserDep,
    session: SessionDep,
    gateway: GatewayDep,
    tz: TimezoneDep,
) -> ScanOut:
    """Finds the tasks in a class message and proposes them. Saves nothing: the learner reviews
    the list and approves it with `POST /class-tasks`. Uses one 'message scan' of the day's AI
    allowance (a message scanned before costs nothing)."""
    today = local_today(review_service.utcnow(), tz)
    return await service.scan_message(session, gateway, user.id, body.text, today)


@router.get("/class-tasks")
async def list_tasks(
    user: CurrentUserDep,
    session: SessionDep,
    tz: TimezoneDep,
    include_done: Annotated[bool, Query(description="Also tasks finished in the last 14 days")] = (
        False
    ),
) -> list[ClassTaskOut]:
    """Open tasks, soonest due first and undated last, then recently finished ones."""
    now = review_service.utcnow()
    today = local_today(now, tz)
    tasks = list(await session.scalars(select(ClassTask).where(ClassTask.user_id == user.id)))
    open_tasks = sorted((t for t in tasks if t.done_at is None), key=service.order_key)
    out = [service.task_out(t, today) for t in open_tasks]
    if include_done:
        done = sorted(
            (t for t in tasks if t.done_at is not None and t.done_at >= now - DONE_VISIBLE),
            key=lambda t: t.done_at or now,
            reverse=True,
        )
        out += [service.task_out(t, today) for t in done]
    return out


@router.post("/class-tasks", status_code=status.HTTP_201_CREATED)
async def create_tasks(
    body: ClassTaskBatchIn, user: CurrentUserDep, session: SessionDep, tz: TimezoneDep
) -> list[ClassTaskOut]:
    """Saves the tasks the learner approved (or one added by hand). All or none."""
    today = local_today(review_service.utcnow(), tz)
    tasks = [ClassTask(user_id=user.id, **item.model_dump()) for item in body.items]
    session.add_all(tasks)
    await session.commit()
    return [service.task_out(t, today) for t in tasks]


@router.patch("/class-tasks/{task_id}")
async def update_task(
    task_id: UUID, body: ClassTaskUpdate, user: CurrentUserDep, session: SessionDep, tz: TimezoneDep
) -> ClassTaskOut:
    """Edit a task, or tick it off with `done`. Ticking it off also clears its reminder."""
    task = await _get_task(session, user.id, task_id)
    changes = body.model_dump(exclude_unset=True)
    nulled = sorted(k for k in _NOT_NULL if k in changes and changes[k] is None)
    if nulled:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"These fields can't be null: {nulled}"
        )
    now = review_service.utcnow()
    done = changes.pop("done", None)
    for field, value in changes.items():
        setattr(task, field, value)
    if done and task.done_at is None:
        task.done_at = now
    elif done is False:
        task.done_at = None
    if task.done_at is not None:
        task.remind_at = None  # nothing left to remind about
    await session.commit()
    return service.task_out(task, local_today(now, tz))


@router.delete("/class-tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: UUID, user: CurrentUserDep, session: SessionDep) -> Response:
    await session.delete(await _get_task(session, user.id, task_id))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
