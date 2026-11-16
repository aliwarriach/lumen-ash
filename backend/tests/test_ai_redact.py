from app.ai.redact import normalize, redact


def test_phone_numbers_are_removed_but_dates_and_page_numbers_are_kept() -> None:
    text = "Ruf mich an: +92 300 1234567 oder 0300-1234567. Test am 12.11.2026, Seite 31-33."
    assert redact(text) == "Ruf mich an: [phone] oder [phone]. Test am 12.11.2026, Seite 31-33."
    assert redact("Meine Nummer ist 030 12345678.") == "Meine Nummer ist [phone]."
    assert redact("Call +4912345 now") == "Call [phone] now"


def test_emails_links_and_mentions_are_removed() -> None:
    text = "Mail ali@example.com, siehe https://wa.me/923001234567 und www.allango.net/a1, @Sara!"
    assert redact(text) == "Mail [email], siehe [link] und [link], [name]!"


def test_whatsapp_sender_names_are_removed_but_the_message_stays() -> None:
    text = "[12/11/26, 10:30] Herr Müller: Hausaufgabe: Seite 31\n12.11.2026, 10:31 - Sara K: ok"
    assert redact(text) == (
        "[12/11/26, 10:30] [name]: Hausaufgabe: Seite 31\n12.11.2026, 10:31 - [name]: ok"
    )


def test_known_names_are_removed_as_whole_words_only() -> None:
    assert (
        redact("Ich heiße Tom und Tomate ist gut.", ["tom"])
        == "Ich heiße [name] und Tomate ist gut."
    )
    assert redact("Ali Warraich lernt.", ["Ali", "Ali Warraich"]) == "[name] lernt."
    assert redact("Ich bin A.", ["A"]) == "Ich bin A."  # one-letter names are ignored


def test_plain_german_is_unchanged() -> None:
    sentence = "Ich habe einen Tisch gekauft. Der Tisch kostet 25 Euro."
    assert redact(sentence) == sentence


def test_normalize_collapses_whitespace_but_keeps_case() -> None:
    assert normalize("  Ich  habe\n einen Tisch ") == "Ich habe einen Tisch"
    assert normalize("ich habe einen tisch") != normalize("Ich habe einen Tisch")
    assert normalize("ü") == normalize("ü")
