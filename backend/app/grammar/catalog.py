"""The A1 grammar patterns the app tracks. Fixed reference content, the same for every learner.

Written as practical patterns, not abstract rules. Every example and correction here should be
checked by a teacher before it changes: the app's corrections are only as good as this list.
"""

from dataclasses import dataclass
from enum import StrEnum


class MistakeCategory(StrEnum):
    """Coarse groups for the mistake log, from the product design."""

    ARTICLE = "article"  # gender, plural, possessive articles
    CONJUGATION = "conjugation"
    WORD_ORDER = "word_order"
    CASE = "case"
    PREPOSITION = "preposition"
    SPELLING = "spelling"
    VOCABULARY = "vocabulary"  # wrong word chosen
    LISTENING = "listening"
    SPEAKING = "speaking"
    OTHER = "other"


class PatternKey(StrEnum):
    VERB_SECOND = "verb_second"
    YES_NO_QUESTIONS = "yes_no_questions"
    W_QUESTIONS = "w_questions"
    NOUN_GENDER = "noun_gender"
    PLURAL_FORMS = "plural_forms"
    ACCUSATIVE = "accusative"
    PRESENT_ENDINGS = "present_endings"
    SEIN_HABEN = "sein_haben"
    STEM_CHANGE = "stem_change"
    SEPARABLE_VERBS = "separable_verbs"
    MODAL_VERBS = "modal_verbs"
    NEGATION = "negation"
    POSSESSIVES = "possessives"
    TIME_PREPOSITIONS = "time_prepositions"
    DATIVE_PREPOSITIONS = "dative_prepositions"
    PERFEKT = "perfekt"
    CAPITALS_SPELLING = "capitals_spelling"


@dataclass(frozen=True)
class Example:
    german: str
    english: str


@dataclass(frozen=True)
class CommonMistake:
    wrong: str
    correct: str
    why: str


@dataclass(frozen=True)
class Practice:
    prompt: str
    answer: str


@dataclass(frozen=True)
class Pattern:
    key: PatternKey
    title: str
    category: MistakeCategory
    explanation: str
    examples: tuple[Example, ...]
    common_mistakes: tuple[CommonMistake, ...]
    practice: tuple[Practice, ...]


_PATTERNS = [
    Pattern(
        PatternKey.VERB_SECOND,
        "Verb in second position",
        MistakeCategory.WORD_ORDER,
        "In a statement the conjugated verb is always the second part of the sentence. If you "
        "start with something other than the subject (a time, a place), the subject moves "
        "to just after the verb.",
        (
            Example("Ich lerne heute Deutsch.", "I'm learning German today."),
            Example("Heute lerne ich Deutsch.", "Today I'm learning German."),
            Example("Am Montag habe ich Kurs.", "On Monday I have class."),
        ),
        (
            CommonMistake(
                "Heute ich lerne Deutsch.",
                "Heute lerne ich Deutsch.",
                "'Heute' is the first part, so the verb comes next and 'ich' follows it.",
            ),
            CommonMistake(
                "Am Abend ich koche.",
                "Am Abend koche ich.",
                "'Am Abend' fills the first position; the verb must be second.",
            ),
        ),
        (
            Practice("Start with 'Morgen': Ich arbeite.", "Morgen arbeite ich."),
            Practice(
                "Start with 'Am Sonntag': Wir spielen Fußball.", "Am Sonntag spielen wir Fußball."
            ),
        ),
    ),
    Pattern(
        PatternKey.YES_NO_QUESTIONS,
        "Verb first in yes/no questions",
        MistakeCategory.WORD_ORDER,
        "A question you answer with ja or nein starts with the conjugated verb. The subject "
        "comes straight after it.",
        (
            Example("Kommst du aus Pakistan?", "Are you from Pakistan?"),
            Example("Hast du heute Zeit?", "Do you have time today?"),
            Example("Sprechen Sie Englisch?", "Do you speak English?"),
        ),
        (
            CommonMistake(
                "Sie sprechen Englisch?",
                "Sprechen Sie Englisch?",
                "A written yes/no question starts with the verb.",
            ),
            CommonMistake(
                "Du hast Zeit?",
                "Hast du Zeit?",
                "Put the verb first, then the subject.",
            ),
        ),
        (
            Practice("Make a question: Du wohnst in Berlin.", "Wohnst du in Berlin?"),
            Practice("Make a question: Sie trinken Kaffee.", "Trinken Sie Kaffee?"),
        ),
    ),
    Pattern(
        PatternKey.W_QUESTIONS,
        "W-questions: question word, then verb",
        MistakeCategory.WORD_ORDER,
        "Questions with wer, wie, was, wo, woher, wohin, wann start with the question word. "
        "The conjugated verb comes second, then the subject.",
        (
            Example("Wie heißt du?", "What's your name?"),
            Example("Woher kommen Sie?", "Where are you from?"),
            Example("Was machst du am Wochenende?", "What are you doing at the weekend?"),
        ),
        (
            CommonMistake(
                "Wo du wohnst?",
                "Wo wohnst du?",
                "After the question word comes the verb, then the subject.",
            ),
            CommonMistake(
                "Wie alt du bist?",
                "Wie alt bist du?",
                "'Wie alt' is the question part; the verb follows it.",
            ),
        ),
        (
            Practice("Ask where Anna lives.", "Wo wohnt Anna?"),
            Practice("Ask someone (du) what they are drinking.", "Was trinkst du?"),
        ),
    ),
    Pattern(
        PatternKey.NOUN_GENDER,
        "Noun gender: der, die, das",
        MistakeCategory.ARTICLE,
        "Every noun is masculine (der), feminine (die) or neuter (das). The gender rarely follows "
        "the meaning, so learn every noun with its article. Some endings help: -ung, -heit, "
        "-keit are always die; -chen is always das.",
        (
            Example("Der Tisch ist neu.", "The table is new."),
            Example("Die Lampe ist teuer.", "The lamp is expensive."),
            Example("Das Buch ist interessant.", "The book is interesting."),
        ),
        (
            CommonMistake(
                "Der Buch ist interessant.",
                "Das Buch ist interessant.",
                "Buch is neuter: das Buch.",
            ),
            CommonMistake(
                "Das Lampe ist alt.",
                "Die Lampe ist alt.",
                "Lampe is feminine: die Lampe.",
            ),
        ),
        (
            Practice("Article? ___ Wohnung", "die Wohnung"),
            Practice("Article? ___ Mädchen", "das Mädchen"),
        ),
    ),
    Pattern(
        PatternKey.PLURAL_FORMS,
        "Plural forms",
        MistakeCategory.ARTICLE,
        "German plurals have several endings (-e, -er, -n, -en, -s, or none) and some add an "
        "umlaut. Learn the plural with the noun. In the plural the article is always die.",
        (
            Example("der Tisch, die Tische", "the table, the tables"),
            Example("das Buch, die Bücher", "the book, the books"),
            Example("Die Kinder spielen.", "The children are playing."),
        ),
        (
            CommonMistake(
                "Ich habe zwei Buch.",
                "Ich habe zwei Bücher.",
                "After a number above one, use the plural: die Bücher.",
            ),
            CommonMistake(
                "Der Kinder spielen.",
                "Die Kinder spielen.",
                "Every plural takes die.",
            ),
        ),
        (
            Practice("Plural? die Lampe", "die Lampen"),
            Practice("Plural? das Kind", "die Kinder"),
        ),
    ),
    Pattern(
        PatternKey.ACCUSATIVE,
        "Accusative case: den, einen",
        MistakeCategory.CASE,
        "The direct object (what you have, buy, see, need) is in the accusative. Only masculine "
        "articles change: der → den, ein → einen, kein → keinen. Feminine, neuter and plural "
        "stay the same. 'Es gibt' also takes the accusative.",
        (
            Example("Ich habe einen Tisch gekauft.", "I bought a table."),
            Example("Ich sehe den Mann.", "I see the man."),
            Example("Es gibt einen Supermarkt.", "There is a supermarket."),
        ),
        (
            CommonMistake(
                "Ich habe ein Tisch gekauft.",
                "Ich habe einen Tisch gekauft.",
                "Tisch is masculine and the object of 'kaufen', so ein becomes einen.",
            ),
            CommonMistake(
                "Ich brauche der Stift.",
                "Ich brauche den Stift.",
                "Stift is masculine and the object of 'brauchen': der becomes den.",
            ),
        ),
        (
            Practice("Complete: Ich trinke ___ Kaffee. (ein)", "Ich trinke einen Kaffee."),
            Practice("Complete: Ich kaufe ___ Lampe. (eine)", "Ich kaufe eine Lampe."),
        ),
    ),
    Pattern(
        PatternKey.PRESENT_ENDINGS,
        "Present-tense verb endings",
        MistakeCategory.CONJUGATION,
        "Regular verbs take these endings on the stem: ich -e, du -st, er/sie/es -t, wir -en, "
        "ihr -t, sie/Sie -en.",
        (
            Example("Ich wohne in Lahore.", "I live in Lahore."),
            Example("Du wohnst in Berlin.", "You live in Berlin."),
            Example("Er wohnt in Wien.", "He lives in Vienna."),
        ),
        (
            CommonMistake(
                "Er wohnen in Berlin.",
                "Er wohnt in Berlin.",
                "With er/sie/es the ending is -t.",
            ),
            CommonMistake(
                "Du lernt Deutsch.",
                "Du lernst Deutsch.",
                "With du the ending is -st.",
            ),
        ),
        (
            Practice("Complete: Wir ___ Deutsch. (lernen)", "Wir lernen Deutsch."),
            Practice("Complete: Sie (she) ___ Tee. (trinken)", "Sie trinkt Tee."),
        ),
    ),
    Pattern(
        PatternKey.SEIN_HABEN,
        "sein and haben",
        MistakeCategory.CONJUGATION,
        "sein and haben are irregular. sein: bin, bist, ist, sind, seid, sind. haben: habe, "
        "hast, hat, haben, habt, haben. Age uses sein: 'Ich bin 25 Jahre alt.'",
        (
            Example("Ich bin Student.", "I'm a student."),
            Example("Er hat ein Auto.", "He has a car."),
            Example("Wir sind müde.", "We're tired."),
        ),
        (
            CommonMistake(
                "Ich habe 25 Jahre alt.",
                "Ich bin 25 Jahre alt.",
                "In German your age is something you are, not have.",
            ),
            CommonMistake(
                "Er hast ein Auto.",
                "Er hat ein Auto.",
                "haben with er/sie/es is hat.",
            ),
        ),
        (
            Practice("Complete: Du ___ nett. (sein)", "Du bist nett."),
            Practice("Complete: Ihr ___ Hunger. (haben)", "Ihr habt Hunger."),
        ),
    ),
    Pattern(
        PatternKey.STEM_CHANGE,
        "Verbs with a vowel change",
        MistakeCategory.CONJUGATION,
        "Some verbs change their vowel with du and er/sie/es only: fahren → du fährst, er fährt; "
        "sprechen → du sprichst, er spricht; lesen → du liest, er liest; essen → du isst, er "
        "isst. The other persons are regular.",
        (
            Example("Er fährt nach Hause.", "He's driving home."),
            Example("Sprichst du Deutsch?", "Do you speak German?"),
            Example("Sie liest ein Buch.", "She's reading a book."),
        ),
        (
            CommonMistake(
                "Er fahrt nach Hause.",
                "Er fährt nach Hause.",
                "fahren changes a → ä with du and er/sie/es.",
            ),
            CommonMistake(
                "Sie sprecht gut Deutsch.",
                "Sie spricht gut Deutsch.",
                "sprechen changes e → i with du and er/sie/es.",
            ),
        ),
        (
            Practice("Complete: Du ___ gern Pizza. (essen)", "Du isst gern Pizza."),
            Practice("Complete: Er ___ den Bus. (nehmen)", "Er nimmt den Bus."),
        ),
    ),
    Pattern(
        PatternKey.SEPARABLE_VERBS,
        "Separable verbs",
        MistakeCategory.WORD_ORDER,
        "Verbs like aufstehen, anrufen and einkaufen split in a statement or question: the main "
        "part is conjugated in its usual place and the prefix goes to the very end.",
        (
            Example("Ich stehe um 7 Uhr auf.", "I get up at 7."),
            Example("Der Zug kommt um 9 Uhr an.", "The train arrives at 9."),
            Example("Rufst du mich morgen an?", "Will you call me tomorrow?"),
        ),
        (
            CommonMistake(
                "Ich aufstehe um 7 Uhr.",
                "Ich stehe um 7 Uhr auf.",
                "The prefix 'auf' separates and goes to the end.",
            ),
            CommonMistake(
                "Ich stehe auf um 7 Uhr.",
                "Ich stehe um 7 Uhr auf.",
                "The prefix goes to the very end, after the time.",
            ),
        ),
        (
            Practice("Make a sentence: ich / einkaufen / am Samstag", "Ich kaufe am Samstag ein."),
            Practice("Make a sentence: er / fernsehen / am Abend", "Er sieht am Abend fern."),
        ),
    ),
    Pattern(
        PatternKey.MODAL_VERBS,
        "Modal verbs: können, müssen, wollen, möchten",
        MistakeCategory.WORD_ORDER,
        "The modal verb is conjugated in second position and the other verb goes to the end as "
        "an infinitive. With ich and er/sie/es, modals have no ending: ich kann, er muss.",
        (
            Example("Ich kann gut schwimmen.", "I can swim well."),
            Example("Ich muss heute arbeiten.", "I have to work today."),
            Example("Möchtest du einen Kaffee trinken?", "Would you like to drink a coffee?"),
        ),
        (
            CommonMistake(
                "Ich muss arbeite heute.",
                "Ich muss heute arbeiten.",
                "The second verb stays an infinitive and goes to the end.",
            ),
            CommonMistake(
                "Er kannt Deutsch sprechen.",
                "Er kann Deutsch sprechen.",
                "With er/sie/es, modal verbs have no -t: er kann.",
            ),
        ),
        (
            Practice(
                "Make a sentence: ich / müssen / Hausaufgaben machen",
                "Ich muss Hausaufgaben machen.",
            ),
            Practice(
                "Make a sentence: wir / wollen / ins Kino gehen", "Wir wollen ins Kino gehen."
            ),
        ),
    ),
    Pattern(
        PatternKey.NEGATION,
        "Negation: nicht and kein",
        MistakeCategory.OTHER,
        "Use kein (keine, keinen) for a noun that would have ein or no article. Use nicht for "
        "everything else: verbs, adjectives, names, and nouns with der/die/das.",
        (
            Example("Ich habe kein Auto.", "I don't have a car."),
            Example("Ich habe keine Zeit.", "I don't have time."),
            Example("Ich bin nicht müde.", "I'm not tired."),
        ),
        (
            CommonMistake(
                "Ich habe nicht ein Auto.",
                "Ich habe kein Auto.",
                "'nicht ein' becomes 'kein'.",
            ),
            CommonMistake(
                "Ich bin kein müde.",
                "Ich bin nicht müde.",
                "müde is an adjective, so use nicht.",
            ),
        ),
        (
            Practice("Say the opposite: Ich habe einen Bruder.", "Ich habe keinen Bruder."),
            Practice("Say the opposite: Das Essen ist gut.", "Das Essen ist nicht gut."),
        ),
    ),
    Pattern(
        PatternKey.POSSESSIVES,
        "Possessive articles: mein, dein, sein, ihr",
        MistakeCategory.ARTICLE,
        "mein, dein, sein, ihr, unser, euer, ihr/Ihr take the same endings as ein: add -e for "
        "feminine nouns and for the plural (meine Schwester, meine Eltern).",
        (
            Example("Das ist mein Bruder.", "This is my brother."),
            Example("Das ist meine Schwester.", "This is my sister."),
            Example("Meine Eltern wohnen in Lahore.", "My parents live in Lahore."),
        ),
        (
            CommonMistake(
                "Das ist mein Schwester.",
                "Das ist meine Schwester.",
                "Schwester is feminine, so mein becomes meine.",
            ),
            CommonMistake(
                "Mein Eltern wohnen in Lahore.",
                "Meine Eltern wohnen in Lahore.",
                "Eltern is plural, so mein becomes meine.",
            ),
        ),
        (
            Practice("Complete: Das ist ___ Mutter. (my)", "Das ist meine Mutter."),
            Practice("Complete: Wo wohnt ___ Bruder? (your, du)", "Wo wohnt dein Bruder?"),
        ),
    ),
    Pattern(
        PatternKey.TIME_PREPOSITIONS,
        "Time: um, am, im",
        MistakeCategory.PREPOSITION,
        "um for clock times (um 8 Uhr); am for days and parts of the day (am Montag, am Abend, "
        "but in der Nacht); im for months and seasons (im Mai, im Sommer).",
        (
            Example("Der Kurs beginnt um 9 Uhr.", "The course starts at 9."),
            Example("Am Montag habe ich Kurs.", "On Monday I have class."),
            Example("Im Sommer ist es heiß.", "It's hot in summer."),
        ),
        (
            CommonMistake(
                "Ich komme am 8 Uhr.",
                "Ich komme um 8 Uhr.",
                "Clock times take um.",
            ),
            CommonMistake(
                "Im Montag habe ich frei.",
                "Am Montag habe ich frei.",
                "Days of the week take am.",
            ),
        ),
        (
            Practice("Complete: ___ Juli fahre ich nach Berlin.", "Im Juli fahre ich nach Berlin."),
            Practice("Complete: Ich stehe ___ 7 Uhr auf.", "Ich stehe um 7 Uhr auf."),
        ),
    ),
    Pattern(
        PatternKey.DATIVE_PREPOSITIONS,
        "mit, bei, zu, von, aus, nach + dative",
        MistakeCategory.PREPOSITION,
        "These prepositions always take the dative: der/das → dem, die → der, plural → den. "
        "Short forms: zu dem → zum, zu der → zur, bei dem → beim, von dem → vom. Cities and "
        "most countries take no article: nach Berlin, aus Pakistan.",
        (
            Example("Ich fahre mit dem Bus.", "I go by bus."),
            Example("Ich gehe zum Arzt.", "I'm going to the doctor."),
            Example("Ich wohne bei meiner Tante.", "I live with my aunt."),
        ),
        (
            CommonMistake(
                "Ich fahre mit der Bus.",
                "Ich fahre mit dem Bus.",
                "der Bus after mit is dative: dem Bus.",
            ),
            CommonMistake(
                "Ich gehe zu der Arzt.",
                "Ich gehe zum Arzt.",
                "der Arzt after zu is dative: zu dem, shortened to zum.",
            ),
        ),
        (
            Practice("Complete: Ich fahre mit ___ Fahrrad. (das)", "Ich fahre mit dem Fahrrad."),
            Practice("Complete: Ich gehe ___ Schule. (zu + die)", "Ich gehe zur Schule."),
        ),
    ),
    Pattern(
        PatternKey.PERFEKT,
        "Perfekt: habe gemacht, bin gefahren",
        MistakeCategory.CONJUGATION,
        "To talk about the past, put haben or sein in second position and the past participle "
        "at the end. Verbs of movement from place to place (gehen, fahren, kommen) and a few "
        "others use sein; most verbs use haben.",
        (
            Example("Ich habe Pizza gegessen.", "I ate pizza."),
            Example("Wir sind nach Berlin gefahren.", "We went to Berlin."),
            Example("Hast du gestern Deutsch gelernt?", "Did you study German yesterday?"),
        ),
        (
            CommonMistake(
                "Ich habe nach Berlin gefahren.",
                "Ich bin nach Berlin gefahren.",
                "fahren is movement from place to place, so it takes sein.",
            ),
            CommonMistake(
                "Ich habe gegessen Pizza.",
                "Ich habe Pizza gegessen.",
                "The past participle goes to the end.",
            ),
        ),
        (
            Practice("In the Perfekt: Ich kaufe Brot.", "Ich habe Brot gekauft."),
            Practice("In the Perfekt: Er geht nach Hause.", "Er ist nach Hause gegangen."),
        ),
    ),
    Pattern(
        PatternKey.CAPITALS_SPELLING,
        "Capital letters and spelling",
        MistakeCategory.SPELLING,
        "Every noun starts with a capital letter, and so does Sie when it means formal 'you'. "
        "Keep the umlauts and ß: schon (already) and schön (beautiful) are different words.",
        (
            Example("Ich habe einen Hund.", "I have a dog."),
            Example("Wie heißen Sie?", "What is your name? (formal)"),
            Example("Das Wetter ist schön.", "The weather is nice."),
        ),
        (
            CommonMistake(
                "Ich habe einen hund.",
                "Ich habe einen Hund.",
                "Hund is a noun, so it needs a capital letter.",
            ),
            CommonMistake(
                "Wie heissen sie?",
                "Wie heißen Sie?",
                "heißen is spelt with ß, and formal Sie has a capital.",
            ),
        ),
        (
            Practice("Correct the capitals: ich trinke gern tee.", "Ich trinke gern Tee."),
            Practice("Correct the capitals: woher kommen sie? (formal)", "Woher kommen Sie?"),
        ),
    ),
]

PATTERNS: dict[PatternKey, Pattern] = {p.key: p for p in _PATTERNS}
