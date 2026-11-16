from app.coach.merge import (
    AiIssue,
    Finding,
    Label,
    LtFinding,
    Source,
    apply_fixes,
    count_sentences,
    locate,
    merge,
    sentence_bounds,
    sentence_with_fix,
)
from app.grammar.catalog import MistakeCategory, PatternKey

TEXT = "Ich habe ein Tisch gekauft. Heute ich lerne Deutsch."


def lt_finding(
    wrong: str = "ein Tisch",
    correct: str = "einen Tisch",
    *,
    reason: str | None = None,
    confidence: float | None = 0.9,
    pattern: PatternKey | None = PatternKey.ACCUSATIVE,
    alternatives: tuple[str, ...] = (),
) -> LtFinding:
    start = TEXT.index(wrong)
    return LtFinding(
        start,
        start + len(wrong),
        wrong,
        correct,
        pattern,
        MistakeCategory.CASE,
        reason,
        "Nachricht",
        confidence,
        alternatives,
    )


def only(findings: list[Finding]) -> Finding:
    assert len(findings) == 1
    return findings[0]


# --- The trust ladder ---


def test_languagetool_plus_our_rules_is_confirmed_and_keeps_the_rule_explanation() -> None:
    f = only(merge(TEXT, [lt_finding(reason="Tisch is masculine.")], []))
    assert f.label == Label.CONFIRMED
    assert f.sources == [Source.LANGUAGETOOL, Source.RULES]
    assert f.explanation == "Tisch is masculine."


def test_the_ai_agreeing_adds_a_source_but_never_changes_a_confirmed_correction() -> None:
    agree = AiIssue("ein Tisch", "einen Tisch", "accusative", "Use einen.")
    clash = AiIssue("ein Tisch", "einem Tisch", "accusative", "Dative.")
    f = only(merge(TEXT, [lt_finding(reason="Because.")], [agree]))
    assert f.sources == [Source.LANGUAGETOOL, Source.RULES, Source.AI]
    g = only(merge(TEXT, [lt_finding(reason="Because.")], [clash]))
    assert g.label == Label.CONFIRMED and g.correct == "einen Tisch"
    assert g.explanation == "Because."


def test_languagetool_alone_is_likely_when_it_is_reasonably_sure_or_does_not_say() -> None:
    assert only(merge(TEXT, [lt_finding(confidence=0.9)], [])).label == Label.LIKELY
    assert only(merge(TEXT, [lt_finding(confidence=None)], [])).label == Label.LIKELY


def test_languagetool_alone_but_unsure_of_itself_is_uncertain() -> None:
    assert only(merge(TEXT, [lt_finding(confidence=0.07)], [])).label == Label.UNCERTAIN


def test_languagetool_and_the_ai_agreeing_is_likely_even_if_languagetool_is_unsure() -> None:
    ai = AiIssue("ein Tisch", "einen  Tisch", "accusative", "Masculine object.")
    f = only(merge(TEXT, [lt_finding(confidence=0.07)], [ai]))  # extra spacing doesn't matter
    assert f.label == Label.LIKELY
    assert f.sources == [Source.LANGUAGETOOL, Source.AI]
    assert f.explanation == "Masculine object."


def test_languagetool_and_the_ai_disagreeing_is_uncertain_and_shows_both_fixes() -> None:
    ai = AiIssue("ein Tisch", "einem Tisch", None, "Dative.")
    f = only(merge(TEXT, [lt_finding(alternatives=("einen Tische",))], [ai]))
    assert f.label == Label.UNCERTAIN
    assert f.correct == "einen Tisch"
    assert f.alternatives == ["einem Tisch", "einen Tische"]


def test_an_error_only_the_ai_found_is_likely_and_takes_its_topic() -> None:
    ai = AiIssue("Heute ich lerne", "Heute lerne ich", "verb_second", "The verb is second.")
    f = only(merge(TEXT, [], [ai]))
    assert f.label == Label.LIKELY and f.sources == [Source.AI]
    assert f.pattern_key == PatternKey.VERB_SECOND
    assert f.category == MistakeCategory.WORD_ORDER
    assert (f.start, f.end) == (TEXT.index("Heute"), TEXT.index("Deutsch") - 1)


def test_an_unknown_topic_leaves_the_pattern_empty() -> None:
    ai = AiIssue("Heute ich lerne", "Heute lerne ich", "made_up_topic")
    f = only(merge(TEXT, [], [ai]))
    assert (f.pattern_key, f.category) == (None, MistakeCategory.OTHER)


def test_ai_findings_that_cannot_be_pointed_to_are_dropped() -> None:
    wrong_text = AiIssue("ein Stuhl", "einen Stuhl")  # not in the text
    same = AiIssue("Tisch", "Tisch")  # nothing to change
    blank = AiIssue("  ", "x")
    assert merge(TEXT, [], [wrong_text, same, blank]) == []
    assert locate("Ich sehe Ich", "Ich") is None  # ambiguous: it appears twice


def test_a_case_only_fix_is_a_real_fix() -> None:
    # "ich" -> "Ich" must not be treated as "no change": capitals are the whole point.
    found = merge("ich lerne.", [], [AiIssue("ich", "Ich", "capitals_spelling")])
    assert [(f.wrong, f.correct) for f in found] == [("ich", "Ich")]


def test_ai_findings_that_overlap_each_other_are_not_repeated() -> None:
    a = AiIssue("Heute ich lerne", "Heute lerne ich")
    b = AiIssue("ich lerne", "lerne ich")
    assert len(merge(TEXT, [], [a, b])) == 1


def test_findings_come_back_in_text_order() -> None:
    ai = AiIssue("Heute ich lerne", "Heute lerne ich")
    found = merge(TEXT, [lt_finding()], [ai])
    assert [f.wrong for f in found] == ["ein Tisch", "Heute ich lerne"]


# --- Sentences and applying fixes ---


def test_the_sentence_with_the_error_is_returned_as_written_and_corrected() -> None:
    f = only(merge(TEXT, [lt_finding(reason="x")], []))
    assert sentence_with_fix(TEXT, f) == (
        "Ich habe ein Tisch gekauft.",
        "Ich habe einen Tisch gekauft.",
    )
    second = only(merge(TEXT, [], [AiIssue("Heute ich lerne", "Heute lerne ich")]))
    assert sentence_with_fix(TEXT, second) == (
        "Heute ich lerne Deutsch.",
        "Heute lerne ich Deutsch.",
    )


def test_sentence_bounds_handle_the_first_and_last_sentence_and_line_breaks() -> None:
    assert sentence_bounds("Eins ohne Punkt", 5, 8) == (0, 15)
    assert sentence_bounds("Eins.\nZwei hier", 8, 10) == (6, 15)


def test_sentences_are_counted_by_punctuation_and_lines() -> None:
    assert count_sentences("Ich bin Ali. Ich wohne hier! Du auch?") == 3
    assert count_sentences("Eins\nZwei\n\nDrei") == 3
    assert count_sentences("Ein Satz ohne Punkt") == 1


def test_apply_fixes_uses_confirmed_and_likely_but_leaves_uncertain_alone() -> None:
    confirmed = only(merge(TEXT, [lt_finding(reason="x")], []))
    likely = only(merge(TEXT, [], [AiIssue("Heute ich lerne", "Heute lerne ich")]))
    uncertain = only(merge(TEXT, [lt_finding(confidence=0.01)], []))
    assert apply_fixes(TEXT, [confirmed, likely]) == (
        "Ich habe einen Tisch gekauft. Heute lerne ich Deutsch."
    )
    assert apply_fixes(TEXT, [uncertain]) is None
    assert apply_fixes(TEXT, []) is None


def test_when_fixes_overlap_the_more_trusted_one_wins() -> None:
    a = only(merge(TEXT, [lt_finding(reason="x")], []))
    overlapping = Finding(
        a.start + 1, a.end, "n Tisch", "m Tisch", Label.LIKELY, [Source.AI], None, a.category, None
    )
    assert apply_fixes(TEXT, [a, overlapping]) == (
        "Ich habe einen Tisch gekauft. Heute ich lerne Deutsch."
    )
