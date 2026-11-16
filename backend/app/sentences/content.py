# ruff: noqa: E501  (lesson content is laid out one exercise per block, not wrapped)
"""Sentence lessons: building German sentences step by step, one lesson per course chapter, on the
chapter's topic. Fixed content, the same for every learner, checked by plain rules: no AI.

Kinds, from easiest to hardest:
  order   put word tiles in order; the English sentence is shown
  bank    the same, with a few extra tiles that don't belong
  choice  pick the right reply or sentence
  fill    type one missing word (a cue is given in brackets)
  frame   guided writing: a sentence frame about yourself, each gap checked by a simple rule

Topics follow Netzwerk neu A1 (the chapter titles of the course's audio). A teacher should check
the German before it changes.
"""

from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum

from app.review.grading import normalize


class SentenceKind(StrEnum):
    ORDER = "order"
    BANK = "bank"
    CHOICE = "choice"
    FILL = "fill"
    FRAME = "frame"


class BlankRule(StrEnum):
    CAPITAL = "capital"  # a name, a place, a noun: starts with a capital letter
    LOWER = "lower"  # an adjective or a verb: starts with a small letter
    ANY = "any"


@dataclass(frozen=True)
class Blank:
    label: str  # what goes in the gap, e.g. "your name"
    example: str
    rule: BlankRule = BlankRule.ANY
    accepted: tuple[str, ...] = ()  # if set, only these (any capitals) are right
    ends_with: str | None = None  # e.g. "e" for a verb in the ich-form


@dataclass(frozen=True)
class SentenceExercise:
    id: str
    kind: SentenceKind
    # order/bank: the English; choice/fill: the German with ___ ; frame: the frame with ___ gaps
    prompt: str
    # Accepted answers, the first is the one shown (frame: a model answer). For order/bank:
    # whole sentences without the final punctuation.
    answers: tuple[str, ...]
    hint: str
    why: str
    english: str | None = None
    options: tuple[str, ...] = ()
    distractors: tuple[str, ...] = ()  # bank only
    blanks: tuple[Blank, ...] = ()  # frame only
    end: str = "."

    @property
    def tiles(self) -> tuple[str, ...]:
        if self.kind in (SentenceKind.ORDER, SentenceKind.BANK):
            return (*self.answers[0].split(" "), *self.distractors)
        return ()


@dataclass(frozen=True)
class Lesson:
    id: str
    book_chapter: int
    title: str
    topic: str
    exercises: tuple[SentenceExercise, ...] = field(default=())


def _order(
    id: str,
    english: str,
    sentence: str,
    hint: str,
    why: str,
    *,
    also: tuple[str, ...] = (),
    end: str = ".",
) -> SentenceExercise:  # noqa: E501
    return SentenceExercise(id, SentenceKind.ORDER, english, (sentence, *also), hint, why, end=end)


def _bank(
    id: str,
    english: str,
    sentence: str,
    distractors: tuple[str, ...],
    hint: str,
    why: str,
    *,
    also: tuple[str, ...] = (),
    end: str = ".",
) -> SentenceExercise:  # noqa: E501
    return SentenceExercise(
        id,
        SentenceKind.BANK,
        english,
        (sentence, *also),
        hint,
        why,
        distractors=distractors,
        end=end,
    )  # noqa: E501


def _choice(
    id: str,
    prompt: str,
    options: tuple[str, ...],
    answer: str,
    hint: str,
    why: str,
    english: str | None = None,
) -> SentenceExercise:  # noqa: E501
    return SentenceExercise(id, SentenceKind.CHOICE, prompt, (answer,), hint, why, english, options)


def _fill(
    id: str, prompt: str, answers: tuple[str, ...], hint: str, why: str, english: str
) -> SentenceExercise:  # noqa: E501
    return SentenceExercise(id, SentenceKind.FILL, prompt, answers, hint, why, english)


def _frame(
    id: str, prompt: str, english: str, blanks: tuple[Blank, ...], model: str, hint: str, why: str
) -> SentenceExercise:  # noqa: E501
    return SentenceExercise(
        id, SentenceKind.FRAME, prompt, (model,), hint, why, english, blanks=blanks
    )  # noqa: E501


LESSONS: tuple[Lesson, ...] = (
    Lesson("k1-hallo", 1, "Guten Tag!", "Saying hello and who you are", (
        _order("k1-1", "My name is Ali.", "Ich heiße Ali",
               "Start with 'Ich', then the verb.", "ich (1) heiße (2) Ali."),
        _order("k1-2", "I come from Pakistan.", "Ich komme aus Pakistan",
               "'aus' means 'from' a country.", "kommen aus + country."),
        _order("k1-3", "Where are you from? (du)", "Woher kommst du",
               "The question word comes first.", "W-word, verb, subject.", end="?"),
        _bank("k1-4", "I live in Berlin.", "Ich wohne in Berlin", ("wohnst", "aus"),
              "Two of the words don't belong. 'ich' takes -e.",
              "ich wohne; 'in' for a city you live in.", also=("In Berlin wohne ich",)),
        _choice("k1-5", "Guten Tag! Wie heißen Sie? – …",
                ("Ich heiße Maria Lopez.", "Ich komme aus Maria.", "Ich wohne Maria."),
                "Ich heiße Maria Lopez.",
                "The question asks for a name.", "'Wie heißen Sie?' is answered with 'Ich heiße …'."),
        _choice("k1-6", "You meet your teacher for the first time. You ask: …",
                ("Wie heißt du?", "Wie heißen Sie?"), "Wie heißen Sie?",
                "Teachers and strangers get the polite form.",
                "'Sie' is polite: use it with adults you don't know well."),
        _order("k1-7", "How are you? (du)", "Wie geht es dir",
               "'Wie geht es …?' + dir for a friend.", "'Wie geht es dir?' (friend), 'Ihnen' (polite).",
               end="?"),
        _fill("k1-8", "Wie geht es ___? – Gut, danke. (polite 'you')", ("Ihnen",),
              "The polite form, with a capital I.", "'Wie geht es Ihnen?' is the polite question.",
              "How are you? – Fine, thanks."),
        _bank("k1-9", "I speak German and English.", "Ich spreche Deutsch und Englisch",
              ("sprichst", "oder"), "Languages start with a capital letter.",
              "ich spreche; languages are written with a capital."),
        _frame("k1-10", "Ich heiße ___. Ich komme aus ___. Ich wohne in ___.", "Introduce yourself.",
               (Blank("your name", "Ali", BlankRule.CAPITAL),
                Blank("your country", "Pakistan", BlankRule.CAPITAL),
                Blank("your city", "Lahore", BlankRule.CAPITAL)),
               "Ich heiße Ali. Ich komme aus Pakistan. Ich wohne in Lahore.",
               "Names, countries and cities start with a capital letter.",
               "Three sentences you can say in class from today."),
    )),
    Lesson("k2-leute", 2, "Leute", "People, jobs and hobbies", (
        _order("k2-1", "She is a teacher.", "Sie ist Lehrerin",
               "No 'eine' before a job in German.", "Jobs take no article: Sie ist Lehrerin."),
        _order("k2-2", "What do you do for a living? (du)", "Was bist du von Beruf",
               "Literally: 'What are you by profession?'", "'Was bist du von Beruf?'", end="?"),
        _bank("k2-3", "I am a student.", "Ich bin Student", ("bist", "ein"),
              "No article before a job.", "Ich bin Student (a woman: Studentin)."),
        _order("k2-4", "Do you like going to the cinema? (du)", "Gehst du gern ins Kino",
               "A yes/no question starts with the verb. 'gern' = like to.",
               "Verb first, then 'du', then 'gern'.", end="?"),
        _choice("k2-5", "Was machst du gern? – …",
                ("Ich spiele gern Fußball.", "Ich gern spiele Fußball.", "Gern ich spiele Fußball."),
                "Ich spiele gern Fußball.",
                "'gern' comes after the verb.", "Verb second, 'gern' straight after it."),
        _bank("k2-6", "In summer I like swimming.", "Im Sommer schwimme ich gern", ("schwimmst", "am"),
              "Start with 'Im Sommer'. Then the verb.", "Time first, verb second: Im Sommer schwimme ich gern.",
              also=("Ich schwimme im Sommer gern", "Ich schwimme gern im Sommer")),
        _fill("k2-7", "Er ___ als Arzt. (arbeiten)", ("arbeitet",),
              "The stem ends in -t: add an extra e.", "er arbeit-e-t.", "He works as a doctor."),
        _order("k2-8", "This is my friend Tom.", "Das ist mein Freund Tom",
               "'Das ist …' introduces someone.", "Das ist + person."),
        _choice("k2-9", "Wie alt ist sie? – …",
                ("Sie ist 25 Jahre alt.", "Sie hat 25 Jahre.", "Sie ist 25 Jahre."),
                "Sie ist 25 Jahre alt.",
                "In German you 'are' an age, and 'alt' comes at the end.",
                "Age: sein + Jahre alt (not 'haben').", "How old is she?"),
        _frame("k2-10", "Ich bin ___ von Beruf. Ich ___ gern.", "Your job and a hobby.",
               (Blank("your job", "Ingenieur", BlankRule.CAPITAL),
                Blank("a verb in the ich-form (e.g. koche, lese)", "koche", BlankRule.LOWER, ends_with="e")),
               "Ich bin Ingenieur von Beruf. Ich koche gern.",
               "A job is a noun (capital). The verb for 'ich' ends in -e.",
               "Now you can say what you do and what you like."),
    )),
    Lesson("k3-stadt", 3, "In der Stadt", "Places and directions", (
        _order("k3-1", "Where is the station?", "Wo ist der Bahnhof",
               "Question word first.", "der Bahnhof = the station.", end="?"),
        _order("k3-2", "The museum is on the left.", "Das Museum ist links",
               "'links' = on the left.", "das Museum; links/rechts at the end."),
        _bank("k3-3", "Go straight ahead, please. (polite)", "Gehen Sie bitte geradeaus", ("Geht", "links"),
              "A polite instruction starts with the verb, then 'Sie'.",
              "Polite imperative: verb + Sie.", also=("Bitte gehen Sie geradeaus",)),
        _choice("k3-4", "Gibt es hier ___ Supermarkt?", ("einen", "ein", "eine"), "einen",
                "'es gibt' takes the accusative. 'Supermarkt' is masculine.",
                "es gibt + einen (masculine).", "Is there a supermarket here?"),
        _choice("k3-5", "Ist das ___ Kirche? – Nein, das ist ein Museum.", ("eine", "ein", "einen"), "eine",
                "'Kirche' is feminine.", "die Kirche → eine Kirche.", "Is that a church? – No, it's a museum."),
        _order("k3-6", "That is not a hotel.", "Das ist kein Hotel",
               "'kein' instead of 'ein' to say 'not a'.", "ein Hotel → kein Hotel."),
        _bank("k3-7", "The station is far away.", "Der Bahnhof ist weit weg", ("Die", "nah"),
              "'Bahnhof' is masculine.", "der Bahnhof; weit weg = far away."),
        _fill("k3-8", "Entschuldigung, wo ___ die Post? (sein)", ("ist",),
              "One place: 'sein' for 'er/sie/es'.", "die Post ist …", "Excuse me, where is the post office?"),
        _order("k3-9", "I'm taking a taxi.", "Ich nehme ein Taxi",
               "nehmen = to take.", "ich nehme; das Taxi → ein Taxi."),
        _frame("k3-10", "Meine Stadt heißt ___. Sie ist ___.", "Describe your town.",
               (Blank("the name of your town", "Lahore", BlankRule.CAPITAL),
                Blank("an adjective (e.g. groß, schön, alt)", "groß", BlankRule.LOWER)),
               "Meine Stadt heißt Lahore. Sie ist groß.",
               "A name gets a capital, an adjective doesn't.",
               "'Sie' here means 'it' (die Stadt)."),
    )),
    Lesson("k4-essen", 4, "Guten Appetit!", "Food and shopping", (
        _order("k4-1", "I'd like a coffee, please.", "Ich möchte bitte einen Kaffee",
               "möchte second, 'einen Kaffee' at the end.", "der Kaffee → einen Kaffee (accusative)."),
        _order("k4-2", "What do you eat for breakfast? (du)", "Was isst du zum Frühstück",
               "'essen' becomes 'isst' with 'du'.", "du isst; zum Frühstück = for breakfast.", end="?"),
        _bank("k4-3", "I don't eat meat.", "Ich esse kein Fleisch", ("nicht", "keinen"),
              "'Fleisch' is neuter (das Fleisch).", "das Fleisch → kein Fleisch."),
        _choice("k4-4", "Was kostet ___ Brot?", ("das", "der", "den"), "das",
                "'Brot' is neuter.", "das Brot.", "How much is the bread?"),
        _choice("k4-5", "Schmeckt's? – …", ("Ja, sehr gut!", "Ja, ich bin gut.", "Ja, ich habe gut."),
                "Ja, sehr gut!", "'Schmeckt's?' = Does it taste good?",
                "Answer about the food: 'Ja, sehr gut!'", "Is it tasty? – …"),
        _bank("k4-6", "We need milk and eggs.", "Wir brauchen Milch und Eier", ("Milchs", "braucht"),
              "The plural of 'Ei' is 'Eier'.", "wir brauchen; das Ei → die Eier."),
        _fill("k4-7", "Ich ___ gern Fisch. (essen)", ("esse",),
              "No vowel change for 'ich'.", "ich esse (only du isst, er isst change).", "I like eating fish."),
        _order("k4-8", "The apples cost two euros.", "Die Äpfel kosten zwei Euro",
               "Plural: 'die Äpfel' and 'kosten'.", "die Äpfel kosten (plural verb)."),
        _choice("k4-9", "Ich hätte gern ___ Kilo Tomaten.", ("ein", "einen", "eine"), "ein",
                "'Kilo' is neuter (das Kilo).", "das Kilo → ein Kilo.", "I'd like a kilo of tomatoes."),
        _frame("k4-10", "Zum Frühstück esse ich ___ und ich trinke ___.", "Your breakfast.",
               (Blank("a food (e.g. Brot, Eier)", "Brot", BlankRule.CAPITAL),
                Blank("a drink (e.g. Tee, Kaffee)", "Tee", BlankRule.CAPITAL)),
               "Zum Frühstück esse ich Brot und ich trinke Tee.",
               "Food and drinks are nouns: capital letters.",
               "'Zum Frühstück' comes first, so 'esse' is second and 'ich' third."),
    )),
    Lesson("k5-tag", 5, "Tag für Tag", "Time, daily routine and family", (
        _order("k5-1", "I get up at six o'clock.", "Ich stehe um sechs Uhr auf",
               "'aufstehen' splits: 'auf' goes to the end.", "stehe … auf."),
        _order("k5-2", "What time is it?", "Wie spät ist es",
               "Literally: 'How late is it?'", "'Wie spät ist es?'", end="?"),
        _bank("k5-3", "On Monday I work until five.", "Am Montag arbeite ich bis fünf Uhr", ("um", "arbeitest"),
              "'bis' = until. Start with the day.", "Day first, verb second: Am Montag arbeite ich …",
              also=("Ich arbeite am Montag bis fünf Uhr",)),
        _choice("k5-4", "Wann beginnt der Kurs? – …", ("Um neun Uhr.", "Am neun Uhr.", "Im neun Uhr."),
                "Um neun Uhr.", "Clock times take 'um'.", "um + clock time.", "When does the course start?"),
        _order("k5-5", "My brother calls me.", "Mein Bruder ruft mich an",
               "'anrufen' splits: 'an' at the end.", "ruft … an."),
        _choice("k5-6", "Hast du am Freitag Zeit? – …",
                ("Ja, am Freitag habe ich Zeit.", "Ja, am Freitag ich habe Zeit."),
                "Ja, am Freitag habe ich Zeit.",
                "'am Freitag' is part 1. What comes next?", "After the time, the verb: habe ich.",
                "Are you free on Friday?"),
        _fill("k5-7", "8:30 – Es ist halb ___.", ("neun",),
              "German counts half towards the next hour.", "8:30 is 'halb neun' (half to nine).",
              "It's half past eight."),
        _bank("k5-8", "My sister has two children.", "Meine Schwester hat zwei Kinder", ("Mein", "haben"),
              "'Schwester' is feminine: meine.", "die Schwester → meine Schwester; sie hat."),
        _order("k5-9", "Can we meet tomorrow?", "Können wir uns morgen treffen",
               "The modal verb first; 'treffen' at the end.", "Können … treffen?", end="?"),
        _frame("k5-10", "Ich stehe um ___ Uhr auf. Am Abend ___ ich.", "Your day.",
               (Blank("a time (e.g. 7 or sieben)", "7"),
                Blank("a verb in the ich-form (e.g. koche, lerne)", "koche", BlankRule.LOWER, ends_with="e")),
               "Ich stehe um 7 Uhr auf. Am Abend koche ich.",
               "The verb for 'ich' ends in -e.",
               "'Am Abend' comes first, so the verb is second and 'ich' after it."),
    )),
    Lesson("k6-freizeit", 6, "Freizeit", "Free time, friends and dates", (
        _order("k6-1", "Today is the third of May.", "Heute ist der dritte Mai",
               "Dates use 'der' + ordinal number.", "der dritte Mai."),
        _order("k6-2", "When is your birthday? (du)", "Wann hast du Geburtstag",
               "In German you 'have' your birthday.", "Geburtstag haben.", end="?"),
        _bank("k6-3", "I can play guitar.", "Ich kann Gitarre spielen", ("spielt", "kannst"),
              "kann second, 'spielen' at the end.", "Modal verb + infinitive at the end."),
        _choice("k6-4", "Kommst du mit ins Kino? – …", ("Ja, gern!", "Ja, ich gern.", "Ja, gern ich komme."),
                "Ja, gern!", "A short, friendly yes.", "'Ja, gern!' = Yes, I'd love to.",
                "Are you coming to the cinema?"),
        _choice("k6-5", "Mein Geburtstag ist ___ 12. Juni.", ("am", "im", "um"), "am",
                "A date (a day) takes 'am'.", "am + date; im + month alone.", "My birthday is on 12 June."),
        _order("k6-6", "We want to go swimming at the weekend.", "Wir wollen am Wochenende schwimmen gehen",
               "wollen second, the two infinitives at the end.", "wollen … schwimmen gehen.",
               also=("Am Wochenende wollen wir schwimmen gehen",)),
        _fill("k6-7", "Ich ___ heute nicht kommen. (können)", ("kann",),
              "'können' with 'ich' has no ending.", "ich kann.", "I can't come today."),
        _bank("k6-8", "My friends live in Hamburg.", "Meine Freunde wohnen in Hamburg", ("Mein", "wohnt"),
              "Plural: meine … wohnen.", "Plural subject, plural verb.",
              also=("In Hamburg wohnen meine Freunde",)),
        _order("k6-9", "At lunchtime I eat in the canteen.", "Mittags esse ich in der Kantine",
               "'Mittags' first, then the verb.", "Time first, verb second.",
               also=("Ich esse mittags in der Kantine",)),
        _frame("k6-10", "Am Wochenende möchte ich ___. Mein Geburtstag ist im ___.", "Plans and your birthday.",
               (Blank("an activity (e.g. Fußball spielen, schwimmen)", "Fußball spielen"),
                Blank("a month", "Mai", BlankRule.CAPITAL,
                      accepted=("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
                                "August", "September", "Oktober", "November", "Dezember"))),
               "Am Wochenende möchte ich Fußball spielen. Mein Geburtstag ist im Mai.",
               "Months start with a capital letter.",
               "möchte + infinitive at the end; im + month."),
    )),
)  # fmt: skip

BY_ID: dict[str, Lesson] = {lesson.id: lesson for lesson in LESSONS}


# --- Checking (mirrored in app/src/features/practice/check.ts) ----------------------------------


def is_correct(ex: SentenceExercise, given: str) -> bool:
    """For every kind but frame. Choices must match exactly; the rest ignore capitals."""
    answer = normalize(given)
    accepted = [normalize(a) for a in ex.answers]
    if ex.kind is SentenceKind.CHOICE:
        return answer in accepted
    return answer.casefold() in {a.casefold() for a in accepted}


def blank_problem(blank: Blank, value: str) -> str | None:
    """Why a frame gap is wrong, or None if it is fine."""
    text = normalize(value)
    if not text:
        return f"Fill in {blank.label}."
    if blank.accepted and text.casefold() not in {a.casefold() for a in blank.accepted}:
        return f"'{text}' isn't one of the words for {blank.label}."
    first = text[0]
    if blank.rule is BlankRule.CAPITAL and first.isalpha() and not first.isupper():
        return f"{blank.label.capitalize()} starts with a capital letter here."
    if blank.rule is BlankRule.LOWER and first.isalpha() and not first.islower():
        return f"{blank.label.capitalize()} starts with a small letter here."
    if blank.ends_with and not text.casefold().endswith(blank.ends_with):
        return f"{blank.label.capitalize()} should end in -{blank.ends_with}."
    return None


def same_tiles(sentence: str, tiles: tuple[str, ...]) -> bool:
    """Whether a sentence uses tiles from the set, each at most once (any capitals)."""
    available = Counter(t.casefold() for t in tiles)
    used = Counter(w.casefold() for w in normalize(sentence).split(" "))
    return all(available[w] >= n for w, n in used.items())
