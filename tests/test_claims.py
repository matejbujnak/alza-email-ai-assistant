from datetime import UTC, datetime, timedelta

from app.claims import LEASE, Claim, decide

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)


def test_new_email_is_acquired():
    assert decide(None, NOW) is Claim.ACQUIRED


def test_answered_email_is_done():
    assert decide({"status": "done", "claimed_at": NOW - timedelta(days=1)}, NOW) is Claim.DONE


def test_fresh_claim_is_in_progress():
    assert decide({"status": "processing", "claimed_at": NOW - timedelta(seconds=30)}, NOW) is Claim.IN_PROGRESS


def test_abandoned_claim_is_taken_over():
    record = {"status": "processing", "claimed_at": NOW - LEASE - timedelta(seconds=1)}
    assert decide(record, NOW) is Claim.ACQUIRED
