"""Our own check of an AI answer, from the dictionary and nothing else.

The AI can never make its own answer "Confirmed". The one thing the dictionary can prove is a
verb ending: in "Ich komme aus Pakistan" the dictionary's present-tense table for *kommen* says
that "ich" goes with "komme". Narrow on purpose: it speaks only when it is sure, and otherwise says
nothing, which leaves the answer "Likely".
"""

import re

from app.coach.rules import PRONOUN_KEYS, DictData, tokens

_GAP = re.compile(r"_{2,}|\.{3,}|…+")
_BRACKETS = re.compile(r"\([^()]*\)")  # the clue printed after the line: "(kommen)"
_ENUMERATOR = re.compile(r"^\s*(?:\d{1,2}|[A-Za-z])[.)]?\s+(?=\S)")
_QUOTED = re.compile(r"['\"‘’“”„‚`]([\wäöüßÄÖÜ ]+)['\"‘’“”„‚`]")


def _lower_tokens(text: str) -> list[str]:
    return [t.lower() for t in tokens(text)]


def _missing_in_order(wanted: list[str], sentence: list[str]) -> int:
    """How many of `wanted` cannot be found in `sentence`, reading both left to right."""
    missing = 0
    position = 0
    for word in wanted:
        try:
            position = sentence.index(word, position) + 1
        except ValueError:
            missing += 1
    return missing


def answer_in_sentence(answer: str, filled: str) -> bool:
    """The answer's words all appear in the filled-in sentence, in order."""
    words = _lower_tokens(answer)
    return bool(words) and _missing_in_order(words, _lower_tokens(filled)) == 0


def sentence_matches_task(task: str, filled: str) -> bool | None:
    """Whether `filled` is the printed line with only its gap filled in.

    None when the line has no gap (a "write a question" task has nothing to compare). One printed
    word may differ in a line of four or more: the photo may have misread a word that the AI
    silently put right."""
    if not _GAP.search(task):
        return None
    printed = _lower_tokens(_GAP.sub(" ", _BRACKETS.sub(" ", _ENUMERATOR.sub("", task))))
    if not printed:
        return None
    allowed = 1 if len(printed) >= 4 else 0
    return _missing_in_order(printed, _lower_tokens(filled)) <= allowed


def hint_gives_answer(hint: str, answer: str) -> bool:
    """The hint contains the answer itself, so it is no longer a hint.

    A longer answer word counts wherever it appears. A short one ("in", "die", "war") is also an
    English word, so it only counts when the hint puts it in quotes."""
    words = _lower_tokens(answer)
    if not words:
        return False
    anywhere = set(_lower_tokens(hint))
    quoted = {w for phrase in _QUOTED.findall(hint) for w in _lower_tokens(phrase)}
    return all(w in (anywhere if len(w) >= 4 else quoted) for w in words)


def verb_candidates(form: str) -> set[str]:
    """Infinitives a conjugated form might come from (komme -> kommen, arbeitet -> arbeiten).

    A guess is harmless: a candidate that is not a verb in the dictionary is never found."""
    f = form.lower()
    found = {f, f + "n"}
    for ending in ("st", "t"):
        if f.endswith(ending) and len(f) > len(ending) + 1:
            stem = f[: -len(ending)]
            found.update({stem + "en", stem + "n"})
    return found


def candidate_lemmas(sentence: str) -> set[str]:
    """Every word that might be a verb's infinitive: what to ask the dictionary for."""
    return {c for t in tokens(sentence) for c in verb_candidates(t)}


def confirm_verb_ending(answer: str, filled: str, data: DictData) -> str | None:
    """A reason if the dictionary proves the whole answer: a single verb form, as used in the
    sentence `filled`, with or without its pronoun ("komme" or "ich komme").

    An answer with anything else in it ("kauft einen") is not proven: the dictionary can't speak
    for the extra word, so nothing is confirmed."""
    words = [w for w in tokens(answer) if w.lower() not in PRONOUN_KEYS]
    if len(words) != 1 or len(tokens(answer)) - len(words) > 1:
        return None
    verb_form = words[0]
    sentence = tokens(filled)
    for i, word in enumerate(sentence):
        if word.lower() != verb_form.lower():
            continue
        # The verb sits next to its pronoun: "ich komme" or, in a question, "kommst du".
        neighbours = [sentence[j] for j in (i - 1, i + 1) if 0 <= j < len(sentence)]
        for pronoun in neighbours:
            keys = PRONOUN_KEYS.get(pronoun.lower())
            if keys is None:
                continue
            for lemma in verb_candidates(word):
                verb = data.verbs.get(lemma)
                if verb and any(verb.present.get(k, "").lower() == word.lower() for k in keys):
                    return (
                        f"With '{pronoun}' the verb {verb.lemma} is '{word}': "
                        f"our dictionary's verb table agrees."
                    )
    return None
