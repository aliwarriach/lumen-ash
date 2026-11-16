"""Parser tests. Entries are hand-written in the shape of the kaikki.org German dump."""

from typing import Any

from app.dictionary.parser import clean_gloss, parse_entry


def noun(word: str, **extra: Any) -> dict[str, Any]:
    return {"word": word, "pos": "noun", "lang_code": "de", **extra}


TISCH = noun(
    "Tisch",
    senses=[
        {
            "glosses": [
                "table (a piece of furniture with a deep surface); specific uses include:",
                "dining table, dinner table",
            ],
            "tags": ["masculine", "strong"],
        },
        {"glosses": ["desk (table used for writing)"], "tags": ["masculine"]},
    ],
    forms=[
        {"form": "Tisches", "tags": ["genitive"]},
        {"form": "Tische", "tags": ["plural"]},
        {"form": "Tische", "tags": ["definite", "nominative", "plural"]},
    ],
    sounds=[
        {"ipa": "/tɪʃ/"},
        {
            "audio": "De-Tisch.ogg",
            "ogg_url": "https://upload.wikimedia.org/x/De-Tisch.ogg",
            "mp3_url": "https://upload.wikimedia.org/x/De-Tisch.ogg.mp3",
        },
    ],
)

AUFSTEHEN = {
    "word": "aufstehen",
    "pos": "verb",
    "lang_code": "de",
    "senses": [{"glosses": ["to get up (move to a standing position)"]}],
    "forms": [
        {"form": "stand auf", "tags": ["past"]},
        {"form": "aufgestanden", "tags": ["participle", "past"]},
        {"form": "haben or sein", "tags": ["auxiliary"]},
        {"form": "sein", "tags": ["auxiliary"]},
        {"form": "stehe auf", "tags": ["first-person", "indicative", "present", "singular"]},
        {"form": "stehst auf", "tags": ["indicative", "present", "second-person", "singular"]},
        {"form": "steht auf", "tags": ["indicative", "present", "singular", "third-person"]},
        {"form": "stehen auf", "tags": ["first-person", "indicative", "plural", "present"]},
        {"form": "steht auf", "tags": ["indicative", "plural", "present", "second-person"]},
        {"form": "stehen auf", "tags": ["indicative", "plural", "present", "third-person"]},
        {
            "form": "aufstehe",
            "tags": ["first-person", "indicative", "present", "singular", "subordinate-clause"],
        },
        {"form": "stehe auf", "tags": ["first-person", "singular", "subjunctive-i"]},
    ],
}


def test_noun_gender_plural_audio_and_clean_meanings() -> None:
    entry = parse_entry(TISCH)
    assert entry is not None
    assert entry.lemma == "Tisch"
    assert entry.genders == ["m"]
    assert entry.plurals == ["Tische"]
    assert entry.meanings == ["table", "desk"]
    assert entry.ipa == "/tɪʃ/"
    assert entry.audio_url == "https://upload.wikimedia.org/x/De-Tisch.ogg.mp3"
    assert entry.verb_forms is None


def test_separable_verb_keeps_main_clause_forms() -> None:
    entry = parse_entry(AUFSTEHEN)
    assert entry is not None
    assert entry.verb_forms == {
        "present": {
            "ich": "stehe auf",
            "du": "stehst auf",
            "er_sie_es": "steht auf",
            "wir": "stehen auf",
            "ihr": "steht auf",
            "sie_Sie": "stehen auf",
        },
        "preterite": "stand auf",
        "past_participle": "aufgestanden",
        "auxiliary": "haben/sein",
        "separable": True,
    }


def test_plural_only_noun_has_no_plural_or_gender() -> None:
    entry = parse_entry(
        noun(
            "Eltern",
            senses=[{"glosses": ["parents"], "tags": ["plural", "plural-only"]}],
            forms=[{"form": "Eltern", "tags": ["definite", "nominative", "plural"]}],
        )
    )
    assert entry is not None
    assert entry.plural_only is True
    assert entry.plurals == []
    assert entry.genders == []


def test_several_genders_are_ordered_der_die_das() -> None:
    entry = parse_entry(
        noun(
            "Joghurt",
            senses=[{"glosses": ["yogurt"], "tags": ["neuter", "masculine", "feminine"]}],
            forms=[
                {"form": "Joghurts", "tags": ["plural"]},
                {"form": "Joghurts", "tags": ["plural"]},
            ],
        )
    )
    assert entry is not None
    assert entry.genders == ["m", "f", "n"]
    assert entry.plurals == ["Joghurts"]


def test_inflected_forms_and_other_languages_are_skipped() -> None:
    form_of = noun(
        "Tische", senses=[{"glosses": ["plural of Tisch"], "form_of": [{"word": "Tisch"}]}]
    )
    assert parse_entry(form_of) is None
    assert parse_entry({**TISCH, "lang_code": "en"}) is None
    assert parse_entry({**TISCH, "pos": "name"}) is None


def test_obsolete_senses_are_dropped_when_others_exist() -> None:
    entry = parse_entry(
        noun(
            "Ding",
            senses=[
                {"glosses": ["assembly"], "tags": ["neuter", "obsolete"]},
                {"glosses": ["thing"], "tags": ["neuter"]},
            ],
        )
    )
    assert entry is not None
    assert entry.meanings == ["thing"]


def test_clean_gloss() -> None:
    assert clean_gloss("to rave (to attend a rave)") == "to rave"
    assert clean_gloss("bank (financial institution (formal))") == "bank"
    assert clean_gloss("As a copulative verb:") == "As a copulative verb"


def test_example_is_the_shortest_real_sentence_from_the_first_sense_that_has_one() -> None:
    entry = parse_entry(
        noun(
            "Tisch",
            senses=[
                {"glosses": ["table"], "tags": ["masculine"]},  # no example: look further
                {
                    "glosses": ["desk"],
                    "tags": ["masculine"],
                    "examples": [
                        {
                            "text": "Er legt die Füße auf den Tisch, wenn er müde ist.",
                            "english": "He puts his feet on the desk when tired.",
                        },
                        {"text": "Der Tisch ist gedeckt.", "english": "The table is set."},
                        {
                            "text": "Ein Zitat aus einem Buch von 1900.",
                            "english": "A quote.",
                            "ref": "Book 1900",
                        },
                        {"text": "Kein Englisch hier vorhanden.", "english": ""},
                    ],
                },
                {
                    "glosses": ["bench"],
                    "examples": [
                        {
                            "text": "Das ist ein anderer Satz.",
                            "english": "That is another sentence.",
                        }
                    ],
                },
            ],
        )
    )
    assert entry is not None
    assert (entry.example_de, entry.example_en) == ("Der Tisch ist gedeckt.", "The table is set.")


def test_no_example_when_none_is_usable() -> None:
    entry = parse_entry(
        noun(
            "Tisch",
            senses=[
                {
                    "glosses": ["table"],
                    "examples": [
                        {"text": "Zu kurz", "english": "Too short"},
                        {
                            "text": "Der [Tisch] ist hier und das ist ein Satz.",
                            "english": "The table is here.",
                        },
                    ],
                }
            ],
        )
    )
    assert entry is not None
    assert entry.example_de is None and entry.example_en is None


def test_inflected_forms_are_kept_for_lookup_but_not_the_auxiliary_or_table_markup() -> None:
    noun_entry = parse_entry(TISCH)
    assert noun_entry is not None
    assert noun_entry.forms == ["Tisches", "Tische"]  # the lemma itself and repeats are dropped

    verb_entry = parse_entry(AUFSTEHEN)
    assert verb_entry is not None
    assert "haben or sein" not in verb_entry.forms and "sein" not in verb_entry.forms
    assert {"stand auf", "aufgestanden", "stehst auf", "aufstehe"} <= set(verb_entry.forms)

    messy = parse_entry(
        noun(
            "Haus",
            senses=[{"glosses": ["house"], "tags": ["neuter"]}],
            forms=[
                {"form": "no-table-tags", "tags": ["table-tags"]},
                {"form": "Häuser", "tags": ["plural"]},
                {"form": "-", "tags": ["plural"]},
                {"form": "Haus 123", "tags": ["genitive"]},
                {"form": "x" * 50, "tags": ["dative"]},
            ],
        )
    )
    assert messy is not None and messy.forms == ["Häuser"]


def test_words_that_do_not_inflect_get_no_forms() -> None:
    entry = parse_entry(
        {
            "word": "schnell",
            "pos": "adv",
            "lang_code": "de",
            "senses": [{"glosses": ["quickly"]}],
            "forms": [{"form": "schneller", "tags": ["comparative"]}],
        }
    )
    assert entry is not None and entry.forms == []
