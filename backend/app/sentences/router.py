import random
import re
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.core.auth import CurrentUserDep
from app.core.database import SessionDep
from app.dictionary.models import DictionaryEntry
from app.sentences.content import BY_ID, LESSONS, Lesson, SentenceExercise, SentenceKind
from app.sentences.models import SentenceResult
from app.sentences.schemas import (
    BlankOut,
    LessonOut,
    LessonResultIn,
    LessonSummaryOut,
    SentenceExerciseOut,
)
from app.vocabulary.models import VocabWord

router = APIRouter(tags=["sentences"])

MY_WORDS = "my-words"
MY_WORDS_TITLE = "From my words"
MY_WORDS_TOPIC = "Real sentences with words you have saved"
MY_WORDS_MAX = 10
# A dictionary example becomes a tile exercise only if it is a short, plain sentence.
_PLAIN = re.compile(r"^[^\W\d_][\w'äöüÄÖÜß ,-]*[.?!]?$")
_MIN_WORDS, _MAX_WORDS = 3, 9


def _exercise_out(ex: SentenceExercise) -> SentenceExerciseOut:
    return SentenceExerciseOut(
        id=ex.id,
        kind=ex.kind,
        prompt=ex.prompt,
        english=ex.english,
        options=list(ex.options),
        tiles=list(ex.tiles),
        distractors=list(ex.distractors),
        blanks=[
            BlankOut(
                label=b.label,
                example=b.example,
                rule=b.rule,
                accepted=list(b.accepted),
                ends_with=b.ends_with,
            )
            for b in ex.blanks
        ],
        answers=list(ex.answers),
        end=ex.end,
        hint=ex.hint,
        why=ex.why,
    )


def example_exercise(
    word_id: UUID, german: str, example: str, english: str
) -> SentenceExercise | None:
    """A tile exercise from a dictionary example sentence, or None if it isn't suitable."""
    text = example.strip()
    if not _PLAIN.match(text):
        return None
    end = text[-1] if text[-1] in ".?!" else "."
    sentence = text.rstrip(".?!").strip()
    words = sentence.split(" ")
    if not _MIN_WORDS <= len(words) <= _MAX_WORDS:
        return None
    return SentenceExercise(
        id=f"w-{word_id}",
        kind=SentenceKind.ORDER,
        prompt=english.strip(),
        answers=(sentence,),
        hint=f"It uses your word '{german}'. Find the verb: it is usually second.",
        why=f"A real example sentence for '{german}' (Wiktionary).",
        end=end,
    )


async def _my_words(session: SessionDep, user_id: UUID) -> list[SentenceExercise]:
    rows = await session.execute(
        select(
            VocabWord.id, VocabWord.german, DictionaryEntry.example_de, DictionaryEntry.example_en
        )
        .join(DictionaryEntry, DictionaryEntry.source_key == VocabWord.dictionary_key)
        .where(
            VocabWord.user_id == user_id,
            DictionaryEntry.example_de.is_not(None),
            DictionaryEntry.example_en.is_not(None),
        )
        .order_by(VocabWord.created_at.desc())
        .limit(50)
    )
    out: list[SentenceExercise] = []
    for word_id, german, example_de, example_en in rows:
        if not example_de or not example_en:
            continue
        ex = example_exercise(word_id, german, example_de, example_en)
        if ex is not None:
            out.append(ex)
        if len(out) >= MY_WORDS_MAX:
            break
    return out


async def _results(session: SessionDep, user_id: UUID) -> dict[str, SentenceResult]:
    rows = await session.scalars(select(SentenceResult).where(SentenceResult.user_id == user_id))
    return {r.lesson_id: r for r in rows}


def _summary(lesson_id: str, chapter: int | None, title: str, topic: str, count: int,
             result: SentenceResult | None) -> LessonSummaryOut:  # fmt: skip
    return LessonSummaryOut(
        id=lesson_id,
        book_chapter=chapter,
        title=title,
        topic=topic,
        exercise_count=count,
        best_right=result.best_right if result else None,
        last_right=result.last_right if result else None,
        rounds=result.rounds if result else 0,
    )


@router.get("/sentences/lessons")
async def list_lessons(user: CurrentUserDep, session: SessionDep) -> list[LessonSummaryOut]:
    """The sentence lessons in course order, then the learner's own words (if they have any
    suitable example sentences), each with the learner's best score."""
    results = await _results(session, user.id)
    out = [
        _summary(x.id, x.book_chapter, x.title, x.topic, len(x.exercises), results.get(x.id))
        for x in LESSONS
    ]
    mine = await _my_words(session, user.id)
    out.append(
        _summary(MY_WORDS, None, MY_WORDS_TITLE, MY_WORDS_TOPIC, len(mine), results.get(MY_WORDS))
    )
    return out


@router.get("/sentences/lessons/{lesson_id}")
async def get_lesson(lesson_id: str, user: CurrentUserDep, session: SessionDep) -> LessonOut:
    if lesson_id == MY_WORDS:
        mine = await _my_words(session, user.id)
        random.shuffle(mine)
        return LessonOut(
            id=MY_WORDS,
            book_chapter=None,
            title=MY_WORDS_TITLE,
            topic=MY_WORDS_TOPIC,
            exercises=[_exercise_out(ex) for ex in mine],
        )
    lesson: Lesson | None = BY_ID.get(lesson_id)
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown lesson")
    return LessonOut(
        id=lesson.id,
        book_chapter=lesson.book_chapter,
        title=lesson.title,
        topic=lesson.topic,
        exercises=[_exercise_out(ex) for ex in lesson.exercises],
    )


@router.post("/sentences/lessons/{lesson_id}/result")
async def save_result(
    lesson_id: str, body: LessonResultIn, user: CurrentUserDep, session: SessionDep
) -> LessonSummaryOut:
    """Records one finished round: keeps the best score and the latest."""
    if lesson_id != MY_WORDS and lesson_id not in BY_ID:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown lesson")
    if body.right > body.total:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "More right than asked")
    stmt = insert(SentenceResult).values(
        user_id=user.id,
        lesson_id=lesson_id,
        best_right=body.right,
        last_right=body.right,
        total=body.total,
        rounds=1,
    )
    await session.execute(
        stmt.on_conflict_do_update(
            constraint="uq_sentence_results_lesson",
            set_={
                "best_right": func.greatest(SentenceResult.best_right, stmt.excluded.best_right),
                "last_right": stmt.excluded.last_right,
                "total": stmt.excluded.total,
                "rounds": SentenceResult.rounds + 1,
            },
        )
    )
    await session.commit()
    result = (await _results(session, user.id))[lesson_id]
    lesson = BY_ID.get(lesson_id)
    if lesson is None:
        return _summary(MY_WORDS, None, MY_WORDS_TITLE, MY_WORDS_TOPIC, body.total, result)
    return _summary(
        lesson.id, lesson.book_chapter, lesson.title, lesson.topic, len(lesson.exercises), result
    )
