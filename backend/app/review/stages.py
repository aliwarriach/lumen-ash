"""Word stages, worked out from review evidence. Each rule is simple enough to explain to the
learner ("Mastered: you used it correctly in your own sentences on 2 different days")."""

from dataclasses import dataclass
from datetime import date

from app.review.models import CardType
from app.vocabulary.models import WordStage

REVIEW_STATE = 2  # fsrs.State.Review: graduated from the short learning steps
USABLE_STABILITY_DAYS = 7.0
MASTERY_SENTENCE_DAYS = 2


@dataclass(frozen=True)
class CardEvidence:
    state: int
    stability: float | None
    reps: int
    last_correct: bool | None  # result of the most recent review, None if never reviewed


@dataclass(frozen=True)
class SentenceEvidence:
    correct_days: set[date]  # learner-local days with a correct sentence
    last_correct: bool | None


STAGE_REASONS = {
    WordStage.NEW: "Not reviewed yet.",
    WordStage.LEARNING: "In your first reviews.",
    WordStage.FAMILIAR: "You recognise it and have produced it correctly.",
    WordStage.USABLE: "You can produce it reliably over at least a week.",
    WordStage.MASTERED: (
        f"You used it correctly in your own sentences on {MASTERY_SENTENCE_DAYS} different days."
    ),
}


def compute_stage(
    cards: dict[CardType, CardEvidence], sentence: SentenceEvidence | None
) -> WordStage:
    if not any(c.reps for c in cards.values()):
        return WordStage.NEW

    recall = cards.get(CardType.RECALL)
    produce = cards.get(CardType.PRODUCE)
    article = cards.get(CardType.ARTICLE)

    familiar = (
        recall is not None
        and recall.state == REVIEW_STATE
        and produce is not None
        and produce.last_correct is True
    )
    if not familiar:
        return WordStage.LEARNING

    assert produce is not None
    usable = (
        produce.state == REVIEW_STATE
        and (produce.stability or 0) >= USABLE_STABILITY_DAYS
        and (article is None or (article.state == REVIEW_STATE and article.last_correct is True))
    )
    if not usable:
        return WordStage.FAMILIAR

    mastered = (
        sentence is not None
        and sentence.last_correct is True
        and len(sentence.correct_days) >= MASTERY_SENTENCE_DAYS
    )
    return WordStage.MASTERED if mastered else WordStage.USABLE
