from app.gmail_client import build_reply


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
    assert reply.get_content().strip() == "Ďakujeme, žltý kôň."
