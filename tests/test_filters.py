import pytest

from app.filters import skip_reason

OWN = "bot@example.com"

GMAIL_PASS = (
    "mx.google.com; dkim=pass header.i=@example.com; "
    "spf=pass smtp.mailfrom=jane@example.com; dmarc=pass (p=NONE) header.from=example.com"
)


def test_regular_customer_email_is_not_skipped(make_email):
    assert skip_reason(make_email(), OWN) is None


def test_own_email_is_skipped(make_email):
    assert skip_reason(make_email(sender="Bot <BOT@example.com>"), OWN) == "sent by this inbox"


@pytest.mark.parametrize(
    "sender",
    ["no-reply@google.com", "noreply@shop.com", "mailer-daemon@mail.com", "DoNotReply@bank.com"],
)
def test_no_reply_senders_are_skipped(make_email, sender):
    assert skip_reason(make_email(sender=sender), OWN) == "no-reply address"


def test_contact_form_with_customer_reply_to_is_not_skipped(make_email):
    email = make_email(sender="noreply@eshop-web.sk", Reply_To="jan.novak@gmail.com")
    assert skip_reason(email, OWN) is None


def test_no_reply_reply_to_is_skipped(make_email):
    email = make_email(sender="news@shop.sk", Reply_To="noreply@shop.sk")
    assert skip_reason(email, OWN) == "no-reply address"


@pytest.mark.parametrize("value", ["auto-replied", "auto-generated"])
def test_auto_submitted_is_skipped(make_email, value):
    assert skip_reason(make_email(Auto_Submitted=value), OWN) == "auto-submitted message"


def test_auto_submitted_no_is_not_skipped(make_email):
    assert skip_reason(make_email(Auto_Submitted="no"), OWN) is None


@pytest.mark.parametrize("value", ["bulk", "list", "junk", "Bulk"])
def test_bulk_precedence_is_skipped(make_email, value):
    assert skip_reason(make_email(Precedence=value), OWN) == "bulk/list precedence"


@pytest.mark.parametrize("header", ["List_Id", "List_Unsubscribe"])
def test_mailing_lists_are_skipped(make_email, header):
    assert skip_reason(make_email(**{header: "<news.example.com>"}), OWN) == "mailing list"


def test_authenticated_email_is_not_skipped(make_email):
    assert skip_reason(make_email(Authentication_Results=GMAIL_PASS), OWN) is None


def test_dmarc_failure_is_skipped(make_email):
    header = "mx.google.com; dkim=fail; spf=pass; dmarc=fail (p=REJECT) header.from=alza.cz"
    assert skip_reason(make_email(Authentication_Results=header), OWN) == "sender not authenticated: DMARC failed"


def test_spf_and_dkim_failure_is_skipped(make_email):
    header = "mx.google.com; dkim=none; spf=softfail; dmarc=none"
    reason = skip_reason(make_email(Authentication_Results=header), OWN)
    assert reason == "sender not authenticated: neither SPF nor DKIM passed"


def test_results_from_other_servers_are_not_trusted(make_email):
    forged = "evil.example; dkim=pass; spf=pass; dmarc=pass"
    reason = skip_reason(make_email(Authentication_Results=forged), OWN)
    assert reason == "sender not authenticated: untrusted authentication results"


def test_only_topmost_authentication_header_is_trusted(make_email):
    # The sender can add a fake "pass" header, but Gmail's own verdict is prepended above it.
    email = make_email(Authentication_Results="mx.google.com; dkim=fail; spf=fail; dmarc=fail")
    email.mime["Authentication-Results"] = GMAIL_PASS
    assert skip_reason(email, OWN) == "sender not authenticated: DMARC failed"
