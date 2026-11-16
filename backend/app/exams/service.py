"""Gathers a learner's evidence for a test and turns it into readiness and a revision plan.

Everything is worked out when requested from rows other features already keep: words and their
stages, grammar evidence, workbook completion, and the results the learner entered.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.course.models import Chapter, ChapterResource, ResourceKind
from app.exams import readiness as rd
from app.exams.models import Exam, ExamResult, ResultKind, exam_result_chapters
from app.exams.readiness import ChapterEvidence, Readiness
from app.exams.revision import Phase, Revision, phase_for, revision_plan, why_chapter
from app.exams.schemas import (
    ChapterReadinessOut,
    ChapterRef,
    ExamDetailOut,
    ExamOut,
    PartOut,
    ReadinessBrief,
    ReadinessOut,
    ResultOut,
    RevisionDayOut,
    RevisionOut,
    SectionOut,
    SkillOut,
)
from app.grammar.catalog import PATTERNS
from app.grammar.models import GrammarChapterLink
from app.grammar.service import MIN_ATTEMPTS, WEAK_BELOW, pattern_stats
from app.vocabulary.forms import WordKind
from app.vocabulary.models import VocabWord, WordStage

EVIDENCE_WINDOW = timedelta(days=90)  # how far back practice results and lost marks count
MAX_PRACTICE_RESULTS = 3
MAX_WORDS_SHOWN = 8
SECURE = {WordStage.USABLE, WordStage.MASTERED}
_STAGE_RANK = {WordStage.NEW: 0, WordStage.LEARNING: 1, WordStage.FAMILIAR: 2}


def local_today(now: datetime, tz: ZoneInfo) -> date:
    return now.astimezone(tz).date()


def _word_name(kind: WordKind, article: str | None, german: str) -> str:
    return f"{article} {german}" if kind == WordKind.NOUN and article else german


def _label(result_kind: ResultKind, title: str | None, taken_on: date) -> str:
    name = title or ("Practice test" if result_kind == ResultKind.PRACTICE else "Test")
    return f"{name} on {taken_on.day} {taken_on:%b}"


async def chapters_in_scope(session: AsyncSession, user_id: UUID, exam: Exam) -> list[Chapter]:
    if not exam.whole_course:
        return list(exam.chapters)
    rows = await session.scalars(
        select(Chapter).where(Chapter.user_id == user_id).order_by(Chapter.number)
    )
    return list(rows)


async def gather_evidence(
    session: AsyncSession,
    user_id: UUID,
    exam: Exam,
    chapters: list[Chapter],
    now: datetime,
    today: date,
) -> tuple[list[ChapterEvidence], list[float], dict[str, float]]:
    """(evidence per chapter, recent practice percentages, average test score per skill)."""
    ids = [c.id for c in chapters]
    if not ids:
        return [], [], {}

    # Words and their stages
    stats: dict[UUID, list[int]] = defaultdict(lambda: [0, 0])  # total, secure
    unsecure: dict[UUID, list[tuple[int, str]]] = defaultdict(list)
    word_rows = await session.execute(
        select(
            VocabWord.chapter_id,
            VocabWord.stage,
            VocabWord.kind,
            VocabWord.article,
            VocabWord.german,
        )
        .where(VocabWord.user_id == user_id, VocabWord.chapter_id.in_(ids))
        .order_by(VocabWord.created_at, VocabWord.id)
    )
    for chapter_id, stage, kind, article, german in word_rows:
        if chapter_id is None:
            continue
        stats[chapter_id][0] += 1
        if stage in SECURE:
            stats[chapter_id][1] += 1
        else:
            name = _word_name(kind, article.value if article else None, german)
            unsecure[chapter_id].append((_STAGE_RANK[stage], name))

    # Grammar: the patterns the learner linked to each chapter
    links: dict[UUID, list] = defaultdict(list)  # type: ignore[type-arg]
    for chapter_id, key in await session.execute(
        select(GrammarChapterLink.chapter_id, GrammarChapterLink.pattern_key).where(
            GrammarChapterLink.user_id == user_id, GrammarChapterLink.chapter_id.in_(ids)
        )
    ):
        links[chapter_id].append(key)
    pattern_data = await pattern_stats(session, user_id, now) if links else {}

    # Workbook exercises
    workbook = {
        chapter_id: (total, done)
        for chapter_id, total, done in await session.execute(
            select(
                ChapterResource.chapter_id,
                func.count(),
                func.count(ChapterResource.completed_at),
            )
            .where(
                ChapterResource.user_id == user_id,
                ChapterResource.kind == ResourceKind.WORKBOOK_EXERCISE,
                ChapterResource.chapter_id.in_(ids),
            )
            .group_by(ChapterResource.chapter_id)
        )
    }

    # Chapters the learner lost marks on in a recent test
    lost: dict[UUID, list[str]] = defaultdict(list)
    lost_rows = await session.execute(
        select(
            exam_result_chapters.c.chapter_id,
            ExamResult.kind,
            ExamResult.title,
            ExamResult.taken_on,
        )
        .join(ExamResult, ExamResult.id == exam_result_chapters.c.result_id)
        .where(
            ExamResult.user_id == user_id,
            exam_result_chapters.c.chapter_id.in_(ids),
            ExamResult.taken_on >= today - EVIDENCE_WINDOW,
        )
        .order_by(ExamResult.taken_on.desc())
    )
    for chapter_id, kind, title, taken_on in lost_rows:
        lost[chapter_id].append(_label(kind, title, taken_on))

    evidence = []
    for c in chapters:
        total, secure = stats[c.id]
        keys = links.get(c.id, [])
        attempts = sum(pattern_data[k].attempts for k in keys)
        correct = sum(pattern_data[k].correct for k in keys)
        weak = [
            PATTERNS[k].title
            for k in keys
            if pattern_data[k].attempts >= MIN_ATTEMPTS
            and (pattern_data[k].accuracy or 0) < WEAK_BELOW
        ]
        wb_total, wb_done = workbook.get(c.id, (0, 0))
        evidence.append(
            ChapterEvidence(
                id=c.id,
                number=c.number,
                title=c.title,
                words_total=total,
                words_secure=secure,
                unsecure_words=[n for _, n in sorted(unsecure[c.id])][:MAX_WORDS_SHOWN],
                patterns_linked=len(keys),
                grammar_attempts=attempts,
                grammar_correct=correct,
                weak_patterns=weak,
                workbook_total=wb_total,
                workbook_done=wb_done,
                lost_marks_in=lost[c.id],
            )
        )

    # Recent practice tests: this test's own, or ones not tied to any test
    recent = list(
        await session.scalars(
            select(ExamResult)
            .where(
                ExamResult.user_id == user_id,
                ExamResult.kind == ResultKind.PRACTICE,
                (ExamResult.exam_id == exam.id) | ExamResult.exam_id.is_(None),
                ExamResult.taken_on >= today - EVIDENCE_WINDOW,
            )
            .order_by(ExamResult.taken_on.desc(), ExamResult.created_at.desc())
            .limit(MAX_PRACTICE_RESULTS)
        )
    )
    percents = [100.0 * r.score / r.max_score for r in recent]
    by_skill: dict[str, list[float]] = defaultdict(list)
    for r in recent:
        for s in r.sections:
            by_skill[s["skill"]].append(100.0 * s["score"] / s["max_score"])
    skill_scores = {skill: sum(v) / len(v) for skill, v in by_skill.items()}
    return evidence, percents, skill_scores


async def readiness_for(
    session: AsyncSession, user_id: UUID, exam: Exam, now: datetime, tz: ZoneInfo
) -> Readiness:
    chapters = await chapters_in_scope(session, user_id, exam)
    evidence, percents, skills = await gather_evidence(
        session, user_id, exam, chapters, now, local_today(now, tz)
    )
    return rd.assess(evidence, percents, exam.target_percent, skills)


# --- Output shapes ---


def _ref(c: Chapter) -> ChapterRef:
    return ChapterRef(id=c.id, number=c.number, title=c.title)


def readiness_out(r: Readiness) -> ReadinessOut:
    return ReadinessOut(
        verdict=r.verdict,
        headline=r.headline,
        target=r.target,
        estimate=r.estimate,
        learning_score=r.learning_score,
        practice_score=r.practice_score,
        recent_score=r.recent_score,
        scope_note=r.scope_note,
        reasons=r.reasons,
        chapters_with_evidence=r.chapters_with_evidence,
        chapters_total=r.chapters_total,
        chapters=[
            ChapterReadinessOut(
                id=c.id,
                number=c.number,
                title=c.title,
                score=c.score,
                detail=c.detail,
                needs_work=c.needs_work,
                parts=[PartOut(name=p.name, score=p.score, detail=p.detail) for p in c.parts],
                unsecure_words=c.unsecure_words,
                weak_patterns=c.weak_patterns,
                lost_marks_in=c.lost_marks_in,
            )
            for c in r.chapters
        ],
        focus_chapter_ids=[c.id for c in r.focus],
        skills=[
            SkillOut(skill=s.skill, score=s.score, detail=s.detail, tracked=s.tracked)
            for s in r.skills
        ],
    )


def revision_out(exam: Exam, rev: Revision) -> RevisionOut:
    return RevisionOut(
        phase=rev.phase,
        schedule=[
            RevisionDayOut(
                day=d.day,
                days_left=d.days_left,
                chapter=ChapterRef(id=d.chapter.id, number=d.chapter.number, title=d.chapter.title),
                minutes=d.minutes,
                why=why_chapter(exam.title, d.days_left, d.chapter),
                words=d.chapter.unsecure_words,
            )
            for d in rev.schedule
        ],
    )


def result_out(r: ExamResult, exam_title: str | None) -> ResultOut:
    return ResultOut(
        id=r.id,
        exam_id=r.exam_id,
        exam_title=exam_title,
        kind=r.kind,
        title=r.title,
        taken_on=r.taken_on,
        score=r.score,
        max_score=r.max_score,
        percent=round(100.0 * r.score / r.max_score, 1),
        sections=[
            SectionOut(
                skill=s["skill"],
                score=s["score"],
                max_score=s["max_score"],
                percent=round(100.0 * s["score"] / s["max_score"], 1),
            )
            for s in r.sections
        ],
        weak_chapters=[_ref(c) for c in r.weak_chapters],
        notes=r.notes,
        created_at=r.created_at,
    )


async def _results_count(session: AsyncSession, user_id: UUID, exam_id: UUID) -> int:
    return (
        await session.scalar(
            select(func.count()).where(ExamResult.user_id == user_id, ExamResult.exam_id == exam_id)
        )
        or 0
    )


async def exam_out(
    session: AsyncSession,
    user_id: UUID,
    exam: Exam,
    now: datetime,
    tz: ZoneInfo,
    readiness: Readiness | None = None,
) -> ExamOut:
    days_left = (exam.exam_date - local_today(now, tz)).days
    if readiness is None and days_left >= 0:
        readiness = await readiness_for(session, user_id, exam, now, tz)
    return ExamOut(
        id=exam.id,
        kind=exam.kind,
        title=exam.title,
        exam_date=exam.exam_date,
        days_left=days_left,
        phase=phase_for(days_left),
        whole_course=exam.whole_course,
        chapters=[_ref(c) for c in exam.chapters],
        target_percent=exam.target_percent,
        notes=exam.notes,
        results_count=await _results_count(session, user_id, exam.id),
        readiness=ReadinessBrief(
            verdict=readiness.verdict, headline=readiness.headline, estimate=readiness.estimate
        )
        if readiness and days_left >= 0
        else None,
    )


async def exam_detail(
    session: AsyncSession, user_id: UUID, exam: Exam, now: datetime, tz: ZoneInfo
) -> ExamDetailOut:
    today = local_today(now, tz)
    days_left = (exam.exam_date - today).days
    readiness = await readiness_for(session, user_id, exam, now, tz) if days_left >= 0 else None
    base = await exam_out(session, user_id, exam, now, tz, readiness)
    results = list(
        await session.scalars(
            select(ExamResult)
            .where(ExamResult.user_id == user_id, ExamResult.exam_id == exam.id)
            .order_by(ExamResult.taken_on.desc(), ExamResult.created_at.desc())
        )
    )
    return ExamDetailOut(
        **base.model_dump(),
        readiness_detail=readiness_out(readiness) if readiness else None,
        revision=revision_out(exam, revision_plan(today, exam.exam_date, readiness.focus))
        if readiness
        else None,
        results=[result_out(r, exam.title) for r in results],
    )


async def next_exam(session: AsyncSession, user_id: UUID, today: date) -> Exam | None:
    """The soonest test that hasn't passed."""
    return await session.scalar(
        select(Exam)
        .where(Exam.user_id == user_id, Exam.exam_date >= today)
        .order_by(Exam.exam_date, Exam.created_at)
        .limit(1)
    )


__all__ = [
    "Phase",
    "chapters_in_scope",
    "exam_detail",
    "exam_out",
    "gather_evidence",
    "local_today",
    "next_exam",
    "readiness_for",
    "readiness_out",
    "result_out",
    "revision_out",
]
