from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import ValidationError
from sqlalchemy import or_, select

from app.core.auth import CurrentUserDep
from app.core.database import SessionDep
from app.course.models import Chapter
from app.vocabulary.models import VocabWord, WordStage
from app.vocabulary.schemas import WordCreate, WordFields, WordOut, WordUpdate

router = APIRouter(tags=["vocabulary"])

_REQUIRED_FIELDS = {"kind", "german", "meaning_en", "plural_only"}


def _to_columns(fields: dict[str, Any]) -> dict[str, Any]:
    """`model_dump()` output -> database values. Nested verb forms are already plain dicts."""
    out = dict(fields)
    if out.get("audio_url") is not None:
        out["audio_url"] = str(out["audio_url"])
    return out


async def _check_chapter(session: SessionDep, user_id: UUID, chapter_id: UUID | None) -> None:
    if chapter_id is None:
        return
    owned = await session.scalar(
        select(Chapter.id).where(Chapter.id == chapter_id, Chapter.user_id == user_id)
    )
    if owned is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown chapter")


async def _get_word(session: SessionDep, user_id: UUID, word_id: UUID) -> VocabWord:
    word = await session.scalar(
        select(VocabWord).where(VocabWord.id == word_id, VocabWord.user_id == user_id)
    )
    if word is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Word not found")
    return word


@router.get("/words")
async def list_words(
    user: CurrentUserDep,
    session: SessionDep,
    chapter_id: UUID | None = None,
    stage: WordStage | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> list[WordOut]:
    query = select(VocabWord).where(VocabWord.user_id == user.id)
    if chapter_id is not None:
        query = query.where(VocabWord.chapter_id == chapter_id)
    if stage is not None:
        query = query.where(VocabWord.stage == stage)
    if q and q.strip():
        pattern = "%" + q.strip().replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
        pattern += "%"
        query = query.where(
            or_(VocabWord.german.ilike(pattern), VocabWord.meaning_en.ilike(pattern))
        )
    words = await session.scalars(query.order_by(VocabWord.created_at.desc()))
    return [WordOut.model_validate(w) for w in words]


@router.post("/words", status_code=status.HTTP_201_CREATED)
async def create_word(body: WordCreate, user: CurrentUserDep, session: SessionDep) -> WordOut:
    await _check_chapter(session, user.id, body.chapter_id)
    word = VocabWord(user_id=user.id, **_to_columns(body.model_dump()))
    session.add(word)
    await session.commit()
    await session.refresh(word)
    return WordOut.model_validate(word)


@router.get("/words/{word_id}")
async def get_word(word_id: UUID, user: CurrentUserDep, session: SessionDep) -> WordOut:
    return WordOut.model_validate(await _get_word(session, user.id, word_id))


@router.patch("/words/{word_id}")
async def update_word(
    word_id: UUID, body: WordUpdate, user: CurrentUserDep, session: SessionDep
) -> WordOut:
    word = await _get_word(session, user.id, word_id)
    changes = body.model_dump(exclude_unset=True)
    nulled = sorted(k for k in _REQUIRED_FIELDS if k in changes and changes[k] is None)
    if nulled:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"These fields can't be null: {nulled}"
        )

    # Validate the word as it will be after the change (e.g. no article on a verb).
    current = WordOut.model_validate(word).model_dump(include=set(WordFields.model_fields))
    try:
        merged = WordFields.model_validate({**current, **changes})
    except ValidationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            [{"loc": e["loc"], "msg": e["msg"]} for e in exc.errors()],
        ) from exc

    if "chapter_id" in changes:
        await _check_chapter(session, user.id, merged.chapter_id)
    for field, value in _to_columns(merged.model_dump(include=set(changes))).items():
        setattr(word, field, value)
    await session.commit()
    await session.refresh(word)
    return WordOut.model_validate(word)


@router.delete("/words/{word_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_word(word_id: UUID, user: CurrentUserDep, session: SessionDep) -> Response:
    word = await _get_word(session, user.id, word_id)
    await session.delete(word)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
