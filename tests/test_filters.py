import pytest

from app.filters import skip_reason

BOT = "bot@example.com"


def test_regular_customer_email_is_not_skipped(make_email):
    assert skip_reason(make_email(), BOT) is None


def test_own_email_is_skipped(make_email):
    assert skip_reason(make_email(sender="Bot <BOT@example.com>"), BOT) == "sent by the bot itself"


@pytest.mark.parametrize(
    "sender",
    ["no-reply@google.com", "noreply@shop.com", "mailer-daemon@mail.com", "DoNotReply@bank.com"],
)
def test_no_reply_senders_are_skipped(make_email, sender):
    assert skip_reason(make_email(sender=sender), BOT) == "no-reply sender"


@pytest.mark.parametrize("value", ["auto-replied", "auto-generated"])
def test_auto_submitted_is_skipped(make_email, value):
    assert skip_reason(make_email(Auto_Submitted=value), BOT) == "auto-submitted message"


def test_auto_submitted_no_is_not_skipped(make_email):
    assert skip_reason(make_email(Auto_Submitted="no"), BOT) is None


@pytest.mark.parametrize("value", ["bulk", "list", "junk", "Bulk"])
def test_bulk_precedence_is_skipped(make_email, value):
    assert skip_reason(make_email(Precedence=value), BOT) == "bulk/list precedence"


@pytest.mark.parametrize("header", ["List_Id", "List_Unsubscribe"])
def test_mailing_lists_are_skipped(make_email, header):
    assert skip_reason(make_email(**{header: "<news.example.com>"}), BOT) == "mailing list"
