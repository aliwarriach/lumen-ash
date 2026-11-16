"""Allango links for the course: the list that every new account starts with, and a tool to load
more.

    python -m app.course.import_links [FILE] [--user-id UUID | --all-users] [--dry-run]

FILE defaults to the bundled list (`data/allango_a1_links.txt`). Each line is
`page | type | title | url`. The chapter comes from the item code in the title (`01-2a` is
chapter 1); a missing chapter is created as "Kapitel N". Items already stored (same chapter,
title and link) are skipped, so the command is safe to re-run. Only links are stored, never
Allango's files.
"""

import argparse
import asyncio
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_sessionmaker
from app.course.models import Chapter, ChapterResource, ResourceKind

BUNDLED_LIST = Path(__file__).parent / "data" / "allango_a1_links.txt"
KINDS = {"audio": ResourceKind.AUDIO, "video": ResourceKind.VIDEO}
# An item code: `01-2a` (exercise) or `02-R1` (review box). The first two digits are the chapter.
CODE = re.compile(r"\b(\d{2})-(?:\d+|R\d+)[a-z]?\b")
PREFIX = re.compile(r"^Netzwerk-A1\s+")


@dataclass(frozen=True)
class Item:
    page: int
    kind: ResourceKind
    title: str
    url: str
    chapter: int


def parse_line(line: str, previous_chapter: int | None = None) -> Item:
    parts = [p.strip() for p in line.split("|")]
    if len(parts) != 4:
        raise ValueError("expected 4 parts: page | type | title | url")
    page_text, kind, title, url = parts
    if not page_text.isdigit():
        raise ValueError(f"page must be a number, got {page_text!r}")
    if kind not in KINDS:
        raise ValueError(f"type must be audio or video, got {kind!r}")
    if not url.startswith("https://"):
        raise ValueError("the link must start with https://")
    code = CODE.search(title)
    if code is not None:
        chapter = int(code.group(1))
    elif "Plattform" in title and previous_chapter is not None:
        # The workbook's review pages ("Plattform 1-3") carry no chapter code. They sit in book
        # order right after the chapter they review, so they join the previous item's chapter.
        chapter = previous_chapter
    else:
        raise ValueError("no item code like 01-2a in the title, so the chapter is unknown")
    return Item(int(page_text), KINDS[kind], PREFIX.sub("", title)[:200], url, chapter)


def parse_file(text: str) -> tuple[list[Item], list[str]]:
    items: list[Item] = []
    problems: list[str] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            items.append(parse_line(line, items[-1].chapter if items else None))
        except ValueError as exc:
            problems.append(f"line {number}: {exc}")
    return items, problems


def bundled_items() -> list[Item]:
    items, problems = parse_file(BUNDLED_LIST.read_text(encoding="utf-8"))
    if problems:  # the file ships with the code, so this is a bug, not bad input
        raise RuntimeError("bundled Allango list is malformed: " + "; ".join(problems))
    return items


async def add_items(
    session: AsyncSession, user_id: UUID, items: list[Item]
) -> tuple[int, int, list[int]]:
    """Adds what is missing to one learner's chapters. Returns (added, skipped, chapters
    created). Does not commit."""
    chapters = {
        c.number: c
        for c in await session.scalars(select(Chapter).where(Chapter.user_id == user_id))
    }
    created: list[int] = []
    for number in sorted({i.chapter for i in items} - chapters.keys()):
        chapter = Chapter(user_id=user_id, number=number, title=f"Kapitel {number}", topics=[])
        session.add(chapter)
        chapters[number] = chapter
        created.append(number)
    await session.flush()

    have = set(
        (
            await session.execute(
                select(
                    ChapterResource.chapter_id, ChapterResource.title, ChapterResource.url
                ).where(ChapterResource.user_id == user_id)
            )
        ).all()
    )
    next_position = {
        chapter_id: position + 1
        for chapter_id, position in (
            await session.execute(
                select(ChapterResource.chapter_id, func.max(ChapterResource.position))
                .where(ChapterResource.user_id == user_id)
                .group_by(ChapterResource.chapter_id)
            )
        ).all()
    }
    added = skipped = 0
    for item in items:
        chapter = chapters[item.chapter]
        if (chapter.id, item.title, item.url) in have:
            skipped += 1
            continue
        position = next_position.get(chapter.id, 0)
        next_position[chapter.id] = position + 1
        session.add(
            ChapterResource(
                user_id=user_id,
                chapter_id=chapter.id,
                kind=item.kind,
                title=item.title,
                reference=f"{'AB ' if item.title.startswith('AB ') else ''}S. {item.page}",
                url=item.url,
                position=position,
            )
        )
        added += 1
    return added, skipped, created


async def seed_new_learner(session: AsyncSession, user_id: UUID) -> None:
    """Gives a learner with no chapters at all the bundled course. A learner who already has
    chapters is left alone, so nothing they changed or deleted comes back."""
    has_chapters = await session.scalar(
        select(Chapter.id).where(Chapter.user_id == user_id).limit(1)
    )
    if has_chapters is not None:
        return
    try:
        await add_items(session, user_id, bundled_items())
        await session.commit()
    except IntegrityError:
        # Two first requests raced; the other one seeded.
        await session.rollback()


async def _run(args: argparse.Namespace) -> int:
    items, problems = parse_file(args.file.read_text(encoding="utf-8"))
    for problem in problems:
        print("skipped", problem, file=sys.stderr)
    if problems:
        print(f"{len(problems)} line(s) could not be read; nothing was loaded.", file=sys.stderr)
        return 1

    async with get_sessionmaker()() as session:
        if args.user_id is not None:
            user_ids = [args.user_id]
        else:
            rows = await session.execute(text("select id from auth.users"))
            user_ids = [row[0] for row in rows]
            if not user_ids or (len(user_ids) > 1 and not args.all_users):
                print(
                    f"found {len(user_ids)} users: pass --user-id or --all-users", file=sys.stderr
                )
                return 1
        for user_id in user_ids:
            added, skipped, created = await add_items(session, user_id, items)
            print(f"{user_id}: added {added}, already there {skipped}, new chapters {created}")
        if args.dry_run:
            await session.rollback()
            print("dry run: nothing was changed")
        else:
            await session.commit()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("file", type=Path, nargs="?", default=BUNDLED_LIST)
    who = parser.add_mutually_exclusive_group()
    who.add_argument("--user-id", type=UUID, help="one learner (default: the only user)")
    who.add_argument("--all-users", action="store_true", help="every account")
    parser.add_argument("--dry-run", action="store_true", help="change nothing")
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
