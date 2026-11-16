"""Unit tests for answer checking and stage rules (no database)."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from app.review.grading import check_article, check_produce, normalize, uses_word
from app.review.models import CardType
from app.review.service import start_of_local_day
from app.review.stages import CardEvidence, SentenceEvidence, compute_stage
from app.vocabulary.forms import Article, WordKind
from app.vocabulary.models import VocabWord, WordStage


def word(**kw: object) -> VocabWord:
    defaults: dict[str, object] = {
        "kind": WordKind.NOUN,
        "german": "Tisch",
        "article": Article.DER,
        "plural": "Tische",
        "plural_only": False,
        "verb_forms": None,
    }
    return VocabWord(**{**defaults, **kw})


AUFSTEHEN = word(
    kind=WordKind.VERB,
    german="aufstehen",
    article=None,
    plural=None,
    verb_forms={
        "present": {"ich": "stehe auf", "er_sie_es": "steht auf"},
        "past_participle": "aufgestanden",
    },
)


# --- Produce ---


def test_produce_accepts_spacing_and_final_punctuation() -> None:
    assert check_produce(word(), "  der   Tisch. ").correct


def test_produce_requires_the_article_and_capital() -> None:
    no_article = check_produce(word(), "Tisch")
    assert not no_article.correct and no_article.feedback == "Include the article: der."
    wrong_article = check_produce(word(), "das Tisch")
    assert wrong_article.feedback == "Wrong article: it's der Tisch."
    lower = check_produce(word(), "der tisch")
    assert not lower.correct and "capital" in (lower.feedback or "")


def test_produce_plural_only_and_verbs() -> None:
    eltern = word(german="Eltern", article=None, plural=None, plural_only=True)
    assert check_produce(eltern, "die Eltern").correct
    assert check_produce(AUFSTEHEN, "aufstehen").correct
    assert not check_produce(AUFSTEHEN, "Aufstehen").correct


# --- Article and plural ---


def test_article_card_checks_both_parts() -> None:
    assert check_article(word(), "der", "Tische").correct
    both_wrong = check_article(word(), "die", "Tischen")
    assert not both_wrong.correct
    assert both_wrong.feedback == "The article is der. The plural is die Tische."
    assert check_article(word(plural=None), "der", None).correct  # no plural to ask about


def test_article_card_for_plural_only_noun() -> None:
    eltern = word(german="Eltern", article=None, plural=None, plural_only=True)
    assert check_article(eltern, "die", None).correct
    assert not check_article(eltern, "der", None).correct


# --- Sentences ---


def test_sentence_must_use_a_form_of_the_word() -> None:
    assert uses_word(word(), "Der Tisch ist groß.")
    assert uses_word(word(), "Wir haben zwei Tische.")
    assert not uses_word(word(), "Der Stuhl ist neu.")
    assert not uses_word(word(), "Das ist ein Tischler.")  # whole words only


def test_separable_verb_counts_when_both_parts_appear() -> None:
    assert uses_word(AUFSTEHEN, "Ich stehe um 7 Uhr auf.")
    assert uses_word(AUFSTEHEN, "Ich bin früh aufgestanden.")
    assert not uses_word(AUFSTEHEN, "Ich stehe hier.")


def test_normalize() -> None:
    assert normalize("  Wie   geht’s?  ") == "Wie geht's"


# --- Stages ---

REVIEW, LEARNING = 2, 1


def card(
    state: int = REVIEW, stability: float = 10, last_correct: bool | None = True
) -> CardEvidence:
    return CardEvidence(state=state, stability=stability, reps=3, last_correct=last_correct)


def test_stage_new_until_reviewed() -> None:
    unreviewed = CardEvidence(state=LEARNING, stability=None, reps=0, last_correct=None)
    assert compute_stage({CardType.RECALL: unreviewed}, None) == WordStage.NEW


def test_stage_ladder() -> None:
    learning = {CardType.RECALL: card(state=LEARNING), CardType.PRODUCE: card()}
    assert compute_stage(learning, None) == WordStage.LEARNING

    familiar = {CardType.RECALL: card(), CardType.PRODUCE: card(stability=3)}
    assert compute_stage(familiar, None) == WordStage.FAMILIAR

    usable = {CardType.RECALL: card(), CardType.PRODUCE: card(stability=8)}
    assert compute_stage(usable, None) == WordStage.USABLE

    one_day = SentenceEvidence({date(2026, 11, 10)}, last_correct=True)
    assert compute_stage(usable, one_day) == WordStage.USABLE
    two_days = SentenceEvidence({date(2026, 11, 10), date(2026, 11, 12)}, last_correct=True)
    assert compute_stage(usable, two_days) == WordStage.MASTERED


def test_stage_drops_after_a_mistake() -> None:
    lapsed = {CardType.RECALL: card(), CardType.PRODUCE: card(last_correct=False)}
    assert compute_stage(lapsed, None) == WordStage.LEARNING

    good = {CardType.RECALL: card(), CardType.PRODUCE: card()}
    failed_sentence = SentenceEvidence({date(2026, 11, 10), date(2026, 11, 12)}, False)
    assert compute_stage(good, failed_sentence) == WordStage.USABLE


def test_stage_needs_article_card_for_nouns() -> None:
    cards = {
        CardType.RECALL: card(),
        CardType.PRODUCE: card(),
        CardType.ARTICLE: card(last_correct=False),
    }
    assert compute_stage(cards, None) == WordStage.FAMILIAR


def test_local_day_start() -> None:
    now = datetime(2026, 11, 10, 20, 30, tzinfo=UTC)  # 01:30 on the 11th in Karachi (UTC+5)
    assert start_of_local_day(now, ZoneInfo("Asia/Karachi")) == datetime(
        2026, 11, 10, 19, 0, tzinfo=UTC
    )
    assert start_of_local_day(now, ZoneInfo("UTC")) == datetime(2026, 11, 10, tzinfo=UTC)
