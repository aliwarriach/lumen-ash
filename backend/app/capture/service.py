"""Finds the tasks in a class message and keeps the ones the learner approves.

Nothing is saved by a scan: it only proposes. The learner reviews every item, fixes the date or
title, and approves; only then is a task stored (see router.py).
"""

import re
from datetime import date, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gateway import AiGateway
from app.ai.prompts import MESSAGE_CAPTURE, MessageCaptureOut
from app.ai.redact import find_links
from app.capture.dates import parse_due
from app.capture.models import ClassTask, TaskKind
from app.capture.schemas import ClassTaskOut, ProposedTaskOut, ScanOut

NOTHING_FOUND = "No tasks found in this message. You can add one by hand."
_PLACEHOLDER = re.compile(r"\[link\]")  # what redaction leaves where a link was


def _key(text: str) -> str:
    return " ".join(text.split()).casefold()


def _clean_title(text: str) -> str:
    return " ".join(_PLACEHOLDER.sub("", text).split())


async def open_task_titles(session: AsyncSession, user_id: UUID) -> set[str]:
    rows = await session.scalars(
        select(ClassTask.title).where(ClassTask.user_id == user_id, ClassTask.done_at.is_(None))
    )
    return {_key(t) for t in rows}


async def scan_message(
    session: AsyncSession,
    gateway: AiGateway,
    user_id: UUID,
    text: str,
    today: date,
) -> ScanOut:
    links = find_links(text)
    result = await gateway.run(user_id, MESSAGE_CAPTURE, {"message": text})
    output = cast(MessageCaptureOut, result.output)

    message_key = _key(text)
    existing = await open_task_titles(session, user_id)
    seen: set[str] = set()
    items: list[ProposedTaskOut] = []
    for item in output.items:
        title = _clean_title(item.text)
        if not title or _key(title) in seen:
            continue
        seen.add(_key(title))
        # The AI must copy the date words. If they aren't in the message it made them up, so the
        # date is dropped and the learner chooses it.
        due_text = item.due if item.due and _key(item.due) in message_key else None
        items.append(
            ProposedTaskOut(
                kind=TaskKind(item.kind),
                title=title,
                due_date=parse_due(due_text, today) if due_text else None,
                due_text=due_text,
                url=links[0] if len(links) == 1 else None,
                duplicate=_key(title) in existing,
            )
        )
    return ScanOut(items=items, links=links, message=None if items else NOTHING_FOUND)


def task_out(task: ClassTask, today: date) -> ClassTaskOut:
    return ClassTaskOut(
        id=task.id,
        kind=task.kind,
        title=task.title,
        due_date=task.due_date,
        due_text=task.due_text,
        days_left=(task.due_date - today).days if task.due_date else None,
        url=task.url,
        remind_at=task.remind_at,
        done=task.done_at is not None,
        done_at=task.done_at,
        created_at=task.created_at,
    )


def order_key(task: ClassTask) -> tuple[bool, date, datetime]:
    """Open tasks: soonest due first, undated last."""
    return (task.due_date is None, task.due_date or date.max, task.created_at)
