from app.coach.languagetool import LtMatch
from app.coach.rules import DictData, NounInfo, VerbInfo, map_rule, verify
from app.coach.service import build_lt_findings
from app.grammar.catalog import MistakeCategory, PatternKey

DATA = DictData(
    nouns={
        "tisch": NounInfo("Tisch", frozenset("m"), frozenset({"Tische"})),
        "haus": NounInfo("Haus", frozenset("n"), frozenset({"Häuser"})),
        "frau": NounInfo("Frau", frozenset("f"), frozenset({"Frauen"})),
        "bruder": NounInfo("Bruder", frozenset("m"), frozenset({"Brüder"})),
        "deutsch": NounInfo("Deutsch", frozenset("n"), frozenset()),
        "band": NounInfo("Band", frozenset("mfn"), frozenset()),  # ambiguous gender
        "schreiben": NounInfo("Schreiben", frozenset("n"), frozenset()),
    },
    verbs={
        "gehen": VerbInfo(
            "gehen",
            {
                "ich": "gehe",
                "du": "gehst",
                "er_sie_es": "geht",
                "wir": "gehen",
                "ihr": "geht",
                "sie_Sie": "gehen",
            },
        )
    },
)


def ok(pattern: PatternKey, wrong: str, right: str, start: bool = False) -> str | None:
    return verify(pattern, wrong, right, DATA, sentence_start=start)


# --- LanguageTool rule -> our pattern ---


def test_languagetool_rules_map_to_our_patterns() -> None:
    assert map_rule("OBJECT_AGREEMENT", "GRAMMAR") == (PatternKey.ACCUSATIVE, MistakeCategory.CASE)
    assert map_rule("SIMPLE_AGREEMENT_NEU", "GRAMMAR")[0] == PatternKey.NOUN_GENDER
    assert map_rule("DE_AGREEMENT2", "GRAMMAR")[0] == PatternKey.NOUN_GENDER
    assert map_rule("UPPERCASE_SENTENCE_START", "CASING")[0] == PatternKey.CAPITALS_SPELLING
    assert map_rule("ANYTHING", "CASING")[0] == PatternKey.CAPITALS_SPELLING
    assert map_rule("VIELZAHL_PLUS_SINGULAR", "GRAMMAR")[0] == PatternKey.PLURAL_FORMS
    assert map_rule("DE_VERBAGREEMENT", "GRAMMAR")[0] == PatternKey.PRESENT_ENDINGS
    assert map_rule("HILFSVERB_HABEN_SEIN", "GRAMMAR")[0] == PatternKey.SEIN_HABEN
    assert map_rule("GERMAN_SPELLER_RULE", "TYPOS") == (None, MistakeCategory.SPELLING)
    assert map_rule("SOMETHING_NEW", "GRAMMAR") == (None, MistakeCategory.OTHER)


# --- Verifiers: confirm only when the dictionary agrees ---


def test_accusative_is_confirmed_for_a_masculine_noun_and_explains_why() -> None:
    reason = ok(PatternKey.ACCUSATIVE, "ein Tisch", "einen Tisch")
    assert reason is not None
    assert "Tisch is masculine (der Tisch)" in reason and "accusative" in reason
    assert ok(PatternKey.ACCUSATIVE, "mein Tisch", "meinen Tisch")
    assert ok(PatternKey.ACCUSATIVE, "der Tisch", "den Tisch")


def test_accusative_is_not_confirmed_when_the_dictionary_cannot_back_it() -> None:
    assert ok(PatternKey.ACCUSATIVE, "ein Haus", "einen Haus") is None  # neuter: no change
    assert ok(PatternKey.ACCUSATIVE, "ein Band", "einen Band") is None  # gender is ambiguous
    assert (
        ok(PatternKey.ACCUSATIVE, "ein Unbekannt", "einen Unbekannt") is None
    )  # not in dictionary
    assert ok(PatternKey.ACCUSATIVE, "ein Tisch", "einem Tisch") is None  # dative, not accusative
    assert ok(PatternKey.ACCUSATIVE, "ein Tisch", "einen Stuhl") is None  # a different noun
    assert (
        verify(PatternKey.ACCUSATIVE, "ein Tisch", "einen Tisch", DictData(), sentence_start=False)
        is None
    )


def test_noun_gender_needs_the_right_article_for_the_nouns_gender() -> None:
    reason = ok(PatternKey.NOUN_GENDER, "Der Haus", "Das Haus", start=True)
    assert reason is not None and "Haus is neuter: das Haus" in reason
    assert ok(PatternKey.NOUN_GENDER, "die Tisch", "der Tisch")
    assert ok(PatternKey.NOUN_GENDER, "der Frau", "die Frau") is None  # der Frau is a valid form
    assert ok(PatternKey.NOUN_GENDER, "der Haus", "die Haus") is None  # fix is wrong too
    assert ok(PatternKey.NOUN_GENDER, "der Band", "das Band") is None  # ambiguous gender


def test_capital_letters() -> None:
    assert ok(PatternKey.CAPITALS_SPELLING, "ich", "Ich", start=True) == (
        "A sentence starts with a capital letter."
    )
    assert "Deutsch is a noun" in (ok(PatternKey.CAPITALS_SPELLING, "deutsch", "Deutsch") or "")
    assert "not a noun" in (ok(PatternKey.CAPITALS_SPELLING, "Lerne", "lerne") or "")
    # Not confirmed: a lowercase word we don't know as a noun, mid-sentence.
    assert ok(PatternKey.CAPITALS_SPELLING, "tasche", "Tasche") is None
    # Not confirmed: the word really is a noun, so lowercase would be wrong.
    assert ok(PatternKey.CAPITALS_SPELLING, "Schreiben", "schreiben") is None
    assert ok(PatternKey.CAPITALS_SPELLING, "ich", "du") is None  # not just a case change


def test_plural_must_be_the_dictionarys_plural() -> None:
    reason = ok(PatternKey.PLURAL_FORMS, "Bruder", "Brüder")
    assert reason is not None and "die Brüder" in reason
    assert ok(PatternKey.PLURAL_FORMS, "Bruder", "Brüdern") is None  # LanguageTool's 2nd idea
    assert ok(PatternKey.PLURAL_FORMS, "Bruder", "Bruders") is None


def test_present_endings_check_the_verb_table_not_languagetools_first_guess() -> None:
    assert ok(PatternKey.PRESENT_ENDINGS, "Er gehen", "Er geht")
    assert ok(PatternKey.PRESENT_ENDINGS, "du gehen", "du gehst")
    assert ok(PatternKey.PRESENT_ENDINGS, "Er gehen", "Er gehe") is None  # subjunctive
    assert ok(PatternKey.PRESENT_ENDINGS, "Er gehen", "Wir gehen") is None  # changes the person
    assert ok(PatternKey.PRESENT_ENDINGS, "Sie gehen", "Sie gehen") is None  # nothing to fix


def test_patterns_without_a_verifier_are_never_confirmed() -> None:
    assert ok(PatternKey.SEIN_HABEN, "habe", "bin") is None
    assert ok(PatternKey.VERB_SECOND, "a b", "b a") is None


# --- Turning LanguageTool matches into findings ---


def lt(start: int, end: int, rule: str, *replacements: str, category: str = "GRAMMAR") -> LtMatch:
    return LtMatch(start, end, rule, category, "Nachricht", replacements, 0.2)


def test_the_first_suggestion_our_rules_confirm_wins_over_languagetools_first() -> None:
    text = "Er gehen nach Hause."
    (finding,) = build_lt_findings(
        text, [lt(0, 8, "DE_VERBAGREEMENT", "Er gehe", "Er geht", "Wir gehen")], DATA
    )
    assert finding.correct == "Er geht"
    assert finding.verified_reason is not None
    assert finding.alternatives == ("Er gehe", "Wir gehen")


def test_an_unconfirmed_match_keeps_languagetools_first_suggestion() -> None:
    (finding,) = build_lt_findings(
        "Ich habe gegangen.", [lt(4, 8, "HILFSVERB_HABEN_SEIN", "bin")], DATA
    )
    assert (finding.correct, finding.verified_reason) == ("bin", None)
    assert finding.pattern_key == PatternKey.SEIN_HABEN


def test_matches_on_removed_personal_details_and_overlaps_are_dropped() -> None:
    text = "[name] gehen nach Hause."
    assert build_lt_findings(text, [lt(0, 6, "GERMAN_SPELLER_RULE", "Name")], DATA) == []
    twice = build_lt_findings(
        "Der Haus ist alt.",
        [lt(0, 8, "SIMPLE_AGREEMENT_NEU", "Das Haus"), lt(4, 8, "OTHER", "Haus!")],
        DATA,
    )
    assert [f.correct for f in twice] == ["Das Haus"]


def test_sentence_start_comes_from_the_text_before_the_match() -> None:
    (first,) = build_lt_findings("ich lerne.", [lt(0, 3, "UPPERCASE_SENTENCE_START", "Ich")], DATA)
    assert first.verified_reason is not None
    # Mid-sentence, an unknown lowercase word isn't confirmed as a noun.
    (mid,) = build_lt_findings("Ich lerne tasche.", [lt(10, 16, "DE_CASE", "Tasche")], DATA)
    assert mid.verified_reason is None
