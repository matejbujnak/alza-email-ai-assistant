import pytest

from app import processor
from app.claims import Claim


@pytest.fixture
def world(monkeypatch, make_email):
    """Fake Gmail, claims and LLM that record what happened."""
    events = []
    state = {"claim": Claim.ACQUIRED, "reply": "Hi"}

    def generate_reply(email):
        if isinstance(state["reply"], Exception):
            raise state["reply"]
        return state["reply"]

    monkeypatch.setattr(processor.claims, "claim", lambda message_id: state["claim"])
    monkeypatch.setattr(processor.claims, "mark_done", lambda message_id: events.append("done"))
    monkeypatch.setattr(processor.claims, "release", lambda message_id: events.append("release"))
    monkeypatch.setattr(processor.gmail_client, "get_email", lambda service, message_id: make_email())
    monkeypatch.setattr(processor.gmail_client, "send_reply", lambda service, email, text: events.append("send"))
    monkeypatch.setattr(processor.gmail_client, "mark_as_read", lambda service, message_id: events.append("read"))
    monkeypatch.setattr(processor, "generate_reply", generate_reply)
    return events, state


def test_acquired_email_is_answered_then_recorded_then_read(world):
    events, _ = world
    processor.process_message(None, "m1", "bot@example.com")
    assert events == ["send", "done", "read"]


def test_email_processed_elsewhere_is_left_alone(world):
    events, state = world
    state["claim"] = Claim.IN_PROGRESS
    processor.process_message(None, "m1", "bot@example.com")
    assert events == []


def test_answered_email_is_only_marked_read(world):
    events, state = world
    state["claim"] = Claim.DONE
    processor.process_message(None, "m1", "bot@example.com")
    assert events == ["read"]


def test_failure_releases_claim_and_leaves_email_unread(world):
    events, state = world
    state["reply"] = RuntimeError("All Gemini models failed")
    with pytest.raises(RuntimeError):
        processor.process_message(None, "m1", "bot@example.com")
    assert events == ["release"]


def test_skipped_email_is_recorded_and_read(world):
    events, _ = world
    processor.process_message(None, "m1", "jane@example.com")
    assert events == ["done", "read"]


def test_emails_are_ignored_before_their_claim_record_expires():
    assert processor.MAX_EMAIL_AGE < processor.claims.RETENTION
