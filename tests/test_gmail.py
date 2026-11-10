import pytest

from app.gmail_client import build_reply, get_credentials, split_quoted_reply


def test_parse_email_extracts_fields(make_email):
    email = make_email(body="Dobrý deň, mám otázku.", subject="Reklamácia", sender="Ján <jan@example.com>")

    assert email.sender == "jan@example.com"
    assert email.reply_to == "jan@example.com"
    assert email.subject == "Reklamácia"
    assert email.body.strip() == "Dobrý deň, mám otázku."
    assert email.message_id == "<original@example.com>"
    assert email.thread_id == "thread-1"


def test_reply_to_header_takes_precedence(make_email):
    email = make_email(Reply_To="Support <support@example.com>")
    assert email.reply_to == "support@example.com"


def test_reply_is_addressed_and_threaded(make_email):
    reply = build_reply(make_email(References="<older@example.com>"), "Thanks")

    assert reply["To"] == "jane@example.com"
    assert reply["In-Reply-To"] == "<original@example.com>"
    assert reply["References"] == "<older@example.com> <original@example.com>"


def test_reply_references_without_previous_chain(make_email):
    reply = build_reply(make_email(), "Thanks")
    assert reply["References"] == "<original@example.com>"


def test_reply_subject_gets_single_re_prefix(make_email):
    assert build_reply(make_email(subject="Order"), "x")["Subject"] == "Re: Order"
    assert build_reply(make_email(subject="RE: Order"), "x")["Subject"] == "RE: Order"


def test_reply_is_marked_as_automatic(make_email):
    assert build_reply(make_email(), "x")["Auto-Submitted"] == "auto-replied"


def test_reply_body_keeps_diacritics(make_email):
    reply = build_reply(make_email(), "Ďakujeme, žltý kôň.")
    assert reply.get_body(("plain",)).get_content().strip() == "Ďakujeme, žltý kôň."


def test_reply_has_html_paragraphs(make_email):
    reply = build_reply(make_email(), "Dobrý deň,\n\n- prvý <bod>\n- druhý\n\nAI Assistant")
    assert reply.get_body(("html",)).get_content().strip() == (
        "<p>Dobrý deň,</p><p>- prvý &lt;bod&gt;<br>- druhý</p><p>AI Assistant</p>"
    )


GMAIL_REPLY = """Ako posudzujete náhodné poškodenie?

On Sun, Nov 8, 2026 at 5:29 PM Matej Alza Bot <matej.alza.bot@gmail.com>
wrote:

> Ahoj,
>
> AlzaCare+ je doplnková servisná služba.
>
"""


OUTLOOK_REPLY = (
    "No dobre a druhá najlepšia vec ?\r\n"
    "________________________________\r\n"
    "From: Matej Alza Bot <matej.alza.bot@gmail.com>\r\n"
    "Sent: 09 November 2026 18:17\r\n"
    "To: Bujnak, Matej <bujnama3@fit.cvut.cz>\r\n"
    "Subject: Re: Test\r\n"
    "\r\n"
    "Dobrý deň,\r\n"
    "AlzaCare+ ponúka dva varianty.\r\n"
)


@pytest.mark.parametrize(
    ("text", "new", "quoted"),
    [
        (GMAIL_REPLY, "Ako posudzujete náhodné poškodenie?", "On Sun, Nov 8, 2026 at 5:29 PM"),
        ("Ďakujem\n\nne 8. 11. 2026 o 17:29 Bot <bot@example.com> napísal(a):\n> Text", "Ďakujem", "napísal(a):\nText"),
        ("Ďakujem\n> Text bez úvodného riadku", "Ďakujem", "Text bez úvodného riadku"),
        ("Tu je chyba:\n> Error 42 occurred", "Tu je chyba:", "Error 42 occurred"),
        (OUTLOOK_REPLY, "No dobre a druhá najlepšia vec ?", "From: Matej Alza Bot"),
        ("Díky\n\nOd: Bot <bot@example.com>\nOdesláno: 9. listopadu 2026 18:17\nPředmět: Re: Test\n\nText", "Díky", "Od: Bot"),
        ("Thanks\n-----Original Message-----\nFrom: Bot\nText", "Thanks", "-----Original Message-----"),
        ("Bez citácie.\n", "Bez citácie.\n", ""),
        ("> citát\nMoja odpoveď\n> ďalší citát\nKoniec", "> citát\nMoja odpoveď\n> ďalší citát\nKoniec", ""),
        ("> Iba preposlaný citát", "> Iba preposlaný citát", ""),
        ("Od: zajtra mám čas.\nStačí?", "Od: zajtra mám čas.\nStačí?", ""),
    ],
    ids=["gmail-wrapped-attribution", "slovak-attribution", "quote-without-attribution", "own-colon-line-kept",
         "outlook", "outlook-czech", "original-message", "no-quote", "interleaved", "only-quote",
         "from-word-without-header"],
)
def test_split_quoted_reply(text, new, quoted):
    new_text, quoted_text = split_quoted_reply(text)
    assert new_text == new
    assert quoted in quoted_text
    assert bool(quoted_text) == bool(quoted)


def test_parsed_email_keeps_quote_separately(make_email):
    email = make_email(body=OUTLOOK_REPLY)
    assert email.body == "No dobre a druhá najlepšia vec ?"
    assert "AlzaCare+ ponúka dva varianty." in email.quoted


def test_missing_token_explains_how_to_log_in(monkeypatch, tmp_path):
    monkeypatch.setenv("GMAIL_TOKEN_FILE", str(tmp_path / "missing.json"))
    with pytest.raises(RuntimeError, match="app.gmail_client login"):
        get_credentials()
