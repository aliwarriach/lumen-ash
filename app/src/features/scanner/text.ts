// Pure helpers for the text the phone read from a photo. No React Native imports, so `npm test`
// can run them.

/** The most the server takes for one exercise (a page of a book, roughly). */
export const MAX_EXERCISE_CHARS = 2400;
/** The server asks for at least this many words before it spends any AI on a photo. */
export const MIN_EXERCISE_WORDS = 3;
/** How a gap is written everywhere: in the AI prompt and in the server's checks. */
export const GAP = "___";

/**
 * Text recognition returns the text in blocks. Joins them into lines the learner can edit:
 * trimmed, no empty blocks, no runs of blank lines.
 */
export function joinBlocks(blocks: readonly string[]): string {
  return blocks
    .map((b) => b.replace(/[ \t]+\n/g, "\n").trim())
    .filter((b) => b.length > 0)
    .join("\n")
    .replace(/\n{3,}/g, "\n\n");
}

/**
 * Every way a printed gap comes out of a photo (or a keyboard) becomes "___": a row of
 * underscores with or without spaces, a row of dots, "…", a row of dashes, a lone underscore.
 *
 * Two gaps side by side with one space between them ("__ __") become one: an underline read in
 * pieces is far more common, and the learner sees the result before it is sent.
 */
export function normalizeGaps(text: string): string {
  return text
    .replace(/…+/g, GAP)
    .replace(/\.(?:[ \t]?\.){2,}/g, GAP)
    .replace(/_(?:[ \t]?_)+/g, GAP)
    .replace(/[-–—](?:[ \t]?[-–—]){2,}/g, GAP)
    .replace(/(^|\s)_(?=\s|$|[.,!?;:])/gm, `$1${GAP}`);
}

// German has no word that starts with "l" and a consonant, except these abbreviations
// (laut, laufend, liebe Grüße, pounds). So "lch", "lst" and "ltalien" are a capital I misread.
const L_ABBREVIATIONS = new Set(["lt", "lfd", "lg", "lb", "lbs"]);

/**
 * Puts right what text recognition typically gets wrong in German, before the learner sees it:
 *
 * - a word split over two lines ("Früh-" / "stück") is joined; "Haupt- und Nebensatz" and
 *   "E-Mail-" / "Adresse" keep their hyphen
 * - "ß" read as a capital B inside a word (heiBe, groB) or as a Greek beta
 * - a capital I read as a small l at the start of a word (lch, lhr, lst) or as "|", and a small l
 *   read as a capital I inside a word (SchuIe)
 * - gaps in any form become "___"
 * - umlauts in one Unicode form
 *
 * Deliberately narrow: each rule fixes something that cannot be correct German, so right text is
 * never changed. The learner still reviews everything.
 */
export function cleanReading(raw: string): string {
  let text = raw.normalize("NFC");

  // Words split across lines. The line break goes; the rest of the next line follows on.
  text = text
    .replace(/(\p{L}{2,})-[ \t]*\n[ \t]*(und|oder|bzw\.?)(?=\s)/gu, "$1- $2")
    .replace(/(\p{L}{2,})-[ \t]*\n[ \t]*(\p{Lu}\p{Ll})/gu, "$1-$2")
    .replace(/(\p{L}{2,})-[ \t]*\n[ \t]*(\p{Ll}{2,})/gu, "$1$2");

  // ß. It only ever follows a vowel, and a capital B never sits there ("eBay" has one letter
  // before it, so it is left alone).
  text = text
    .replace(/β/g, "ß")
    .replace(/(\p{L}[aeiouäöü])B(?=\p{Ll}|(?!\p{L}))/gu, "$1ß");

  // Capital I and small l.
  text = text
    .replace(/(^|[^\p{L}\p{N}])([l|])([bcdfghjkmnpqrstvwxzß]\p{L}*)/gmu, (whole, before, first, rest) => {
      const word = `l${rest}`.toLowerCase();
      if (first === "l" && (L_ABBREVIATIONS.has(word) || /^l+$/.test(word))) return whole;
      return `${before}I${rest}`;
    })
    .replace(/(\p{Ll})I(?=\p{Ll})/gu, "$1l");

  return normalizeGaps(text)
    .replace(/[ \t]{2,}/g, " ")
    .replace(/[ \t]+\n/g, "\n")
    .trim();
}

/** What is sent: the learner's text as typed, with gaps and Unicode in the one agreed form. */
export function forSending(text: string): string {
  return normalizeGaps(text.normalize("NFC")).trim();
}

export function wordCount(text: string): number {
  return text.split(/\s+/).filter(Boolean).length;
}

const EDGE_PUNCTUATION = /^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu;
// Inside a word these are normal in a textbook: der/die, Lehrer(in), Lehrer*innen, z.B., E-Mail,
// anna@web.de, 9.30. Anything else inside a word is a misread.
const ODD_INSIDE = /[^\p{L}\p{N}'’.\-/():*@&+,]/u;
// Letters and digits together that are fine: A1, B2, 2a, 10b, S.24.
const FINE_MIXED = /^(?:\p{L}{1,2}\.?\d{1,3}|\d{1,3}\p{L}{1,2})$/u;

function looksOdd(word: string): boolean {
  if (word.includes("@")) return false;
  if (ODD_INSIDE.test(word)) return true;
  const hasLetter = /\p{L}/u.test(word);
  if (hasLetter && /\d/.test(word)) return !FINE_MIXED.test(word);
  if (!hasLetter) return false;
  if (/(.)\1{3,}/u.test(word)) return true; // "lllll"
  if (/\p{Ll}\p{Lu}/u.test(word)) return true; // "hEute"
  const letters = word.replace(/[^\p{L}]/gu, "");
  const shouted = letters === letters.toUpperCase(); // DVD, PKW
  return letters.length >= 4 && !shouted && !/[aeiouyäöü]/i.test(letters);
}

/**
 * How much of the text looks misread: words with a symbol inside them, letters mixed with digits,
 * no vowel, or a capital in the middle. Run on cleaned text. Gaps and plain numbers don't count.
 */
export function readingQuality(text: string): { words: number; odd: number } {
  let words = 0;
  let odd = 0;
  for (const raw of text.split(/\s+/)) {
    const word = raw.replace(/_+/g, "").replace(EDGE_PUNCTUATION, "");
    if (!word || /^\d+(?:[.,:]\d+)*$/.test(word)) continue;
    words += 1;
    if (looksOdd(word)) odd += 1;
  }
  return { words, odd };
}

/** A few odd words are normal (WhatsApp, a name). Many means the photo was read badly. */
export function looksMisread(text: string): boolean {
  const { words, odd } = readingQuality(text);
  return odd >= 3 && odd / words >= 0.15;
}

export type ReadingNote = { text: string; severity: "info" | "warning" };

/**
 * What to tell the learner about the text before it is sent: too little, too much, badly read,
 * no gaps, or fine. `null` means nothing to say. Worked out from the text itself, so the note
 * goes away as the learner puts the text right.
 */
export function reviewNote(text: string): ReadingNote | null {
  const words = wordCount(text);
  if (words === 0) return null;
  if (words < MIN_EXERCISE_WORDS) {
    return { text: "There is hardly any text. Take the photo again, closer and in good light.", severity: "warning" };
  }
  if (text.length > MAX_EXERCISE_CHARS) {
    return {
      text: `This is longer than one exercise (${text.length} of ${MAX_EXERCISE_CHARS} characters). Delete the parts you don't need.`,
      severity: "warning",
    };
  }
  if (looksMisread(text)) {
    return {
      text: "A lot of this looks misread, so the answers would be unreliable. Take the photo again (closer, in good light, page flat, no shadow) or correct the text here first.",
      severity: "warning",
    };
  }
  if (!normalizeGaps(text).includes(GAP)) {
    return {
      text: `No gaps found. If the exercise has gaps, type ${GAP} where each word is missing: photos often lose them.`,
      severity: "info",
    };
  }
  return null;
}

/** Whether the text can be sent as it is. */
export function canSend(text: string): boolean {
  return wordCount(text) >= MIN_EXERCISE_WORDS && text.length <= MAX_EXERCISE_CHARS;
}
