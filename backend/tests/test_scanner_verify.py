from app.coach.rules import DictData, VerbInfo
from app.scanner.verify import candidate_lemmas, confirm_verb_ending, verb_candidates

DATA = DictData(
    verbs={
        "kommen": VerbInfo(
            "kommen", {"ich": "komme", "du": "kommst", "er_sie_es": "kommt", "wir": "kommen"}
        ),
        "arbeiten": VerbInfo(
            "arbeiten", {"ich": "arbeite", "du": "arbeitest", "er_sie_es": "arbeitet"}
        ),
    }
)


def test_lemma_guesses_cover_the_regular_endings() -> None:
    assert "kommen" in verb_candidates("komme")
    assert "kommen" in verb_candidates("kommst")
    assert "kommen" in verb_candidates("kommt")
    assert "arbeiten" in verb_candidates("arbeitet")
    assert "arbeiten" in verb_candidates("arbeitest")
    assert "kommen" in candidate_lemmas("Ich komme aus Pakistan.")


def test_a_verb_ending_next_to_its_pronoun_is_confirmed() -> None:
    assert confirm_verb_ending("komme", "Ich komme aus Pakistan.", DATA)
    assert confirm_verb_ending("kommst", "Woher kommst du?", DATA)  # the pronoun comes after
    assert confirm_verb_ending("arbeitet", "Er arbeitet heute.", DATA)
    assert confirm_verb_ending("ich komme", "Ich komme aus Pakistan.", DATA)
    reason = confirm_verb_ending("kommen", "Wir kommen aus Pakistan.", DATA)
    assert reason and "kommen" in reason and "'Wir'" in reason


def test_a_wrong_ending_is_never_confirmed() -> None:
    assert confirm_verb_ending("kommt", "Ich kommt aus Pakistan.", DATA) is None
    assert confirm_verb_ending("komme", "Er komme aus Pakistan.", DATA) is None


def test_it_stays_silent_when_it_cannot_be_sure() -> None:
    # Extra words in the answer that the dictionary can't speak for.
    assert confirm_verb_ending("kommt aus", "Er kommt aus Pakistan.", DATA) is None
    # No pronoun beside the verb, an unknown verb, or no sentence to look at.
    assert confirm_verb_ending("kommt", "Anna kommt aus Pakistan.", DATA) is None
    assert confirm_verb_ending("fahre", "Ich fahre nach Hause.", DATA) is None
    assert confirm_verb_ending("komme", "Ich gehe.", DATA) is None
    assert confirm_verb_ending("", "Ich komme.", DATA) is None
    assert confirm_verb_ending("komme", "Ich komme.", DictData()) is None
