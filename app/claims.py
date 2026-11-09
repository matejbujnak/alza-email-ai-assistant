"""Firestore records that make sure each email is answered once, even with concurrent instances."""

from datetime import UTC, datetime, timedelta
from enum import Enum
from functools import cache

from google.cloud import firestore

COLLECTION = "processed_emails"
# A claim older than this is treated as abandoned (e.g. the instance crashed) and can be taken over.
LEASE = timedelta(minutes=5)
# A Firestore TTL policy on expire_at deletes the records after this period.
RETENTION = timedelta(days=30)


class Claim(Enum):
    ACQUIRED = "acquired"
    IN_PROGRESS = "in_progress"
    DONE = "done"


def decide(record: dict | None, now: datetime) -> Claim:
    if record is None:
        return Claim.ACQUIRED
    if record["status"] == "done":
        return Claim.DONE
    if now - record["claimed_at"] > LEASE:
        return Claim.ACQUIRED
    return Claim.IN_PROGRESS


@cache
def get_db() -> firestore.Client:
    return firestore.Client()


def _document(message_id: str) -> firestore.DocumentReference:
    return get_db().collection(COLLECTION).document(message_id)


def claim(message_id: str) -> Claim:
    document = _document(message_id)

    # The transaction makes read-and-claim atomic: of two concurrent instances only one acquires it.
    @firestore.transactional
    def run(transaction: firestore.Transaction) -> Claim:
        snapshot = document.get(transaction=transaction)
        now = datetime.now(UTC)
        result = decide(snapshot.to_dict() if snapshot.exists else None, now)
        if result is Claim.ACQUIRED:
            transaction.set(document, {"status": "processing", "claimed_at": now, "expire_at": now + RETENTION})
        return result

    return run(get_db().transaction())


def mark_done(message_id: str) -> None:
    _document(message_id).update({"status": "done"})


def release(message_id: str) -> None:
    _document(message_id).delete()
