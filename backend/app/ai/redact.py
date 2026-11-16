"""Strips personal details from text before it is sent to an AI provider.

What this catches: phone numbers, email addresses, links, @mentions, the sender name at the start
of a WhatsApp line, and any names we're told about (settings, or passed per call).
What it cannot catch: an arbitrary name in running text. German capitalises every noun, so
"Tisch" and "Tom" look the same without a name list. Don't treat this as a privacy guarantee.
"""

import re
import unicodedata
from collections.abc import Iterable

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_URL = re.compile(r"(?:https?://|www\.)\S*[^\s.,;:!?)]", re.IGNORECASE)
# "[12/11/26, 10:30] Ali: hello" or "12.11.2026, 10:30 - Ali: hello"
_WHATSAPP_SENDER = re.compile(
    r"^(?P<head>\[?\d{1,2}[./]\d{1,2}[./]\d{2,4},?\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap][Mm])?\]?"
    r"\s*-?\s*)(?P<name>[^:\n]{1,40}):",
    re.MULTILINE,
)
_MENTION = re.compile(r"@[\w.]+")
# Digits joined by at most two spaces, dots, dashes or brackets. Never across a line break.
_PHONE = re.compile(r"(?<!\w)\+?\d(?:[ ().-]{0,2}\d){6,}")


def _phone(match: re.Match[str]) -> str:
    digits = sum(c.isdigit() for c in match.group())
    # A date like 12.11.2026 has 8 digits; real phone numbers have more, or start with "+".
    if digits >= 9 or (match.group().startswith("+") and digits >= 7):
        return "[phone]"
    return match.group()


def find_links(text: str) -> list[str]:
    """Web links in the text, in order, without repeats. Links are never sent to an AI provider
    (see `redact`), so the ones a class message holds are found here instead."""
    links: dict[str, None] = {}
    for match in _URL.finditer(text):
        link = match.group()
        links[link if link.lower().startswith("http") else f"https://{link}"] = None
    return list(links)


def redact(text: str, names: Iterable[str] = ()) -> str:
    text = _EMAIL.sub("[email]", text)
    text = _URL.sub("[link]", text)
    text = _WHATSAPP_SENDER.sub(lambda m: f"{m['head']}[name]:", text)
    text = _MENTION.sub("[name]", text)
    text = _PHONE.sub(_phone, text)
    for name in sorted({n.strip() for n in names if len(n.strip()) >= 2}, key=len, reverse=True):
        text = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", "[name]", text, flags=re.IGNORECASE)
    return text


def normalize(text: str) -> str:
    """Canonical form for cache keys. Keeps letter case: German capitals matter."""
    return " ".join(unicodedata.normalize("NFC", text).split())
