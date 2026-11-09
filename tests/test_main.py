import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main.gmail_client, "get_gmail_service", lambda: "service")
    return TestClient(main.app)


def test_notification_processes_unread_emails(monkeypatch, client):
    calls = []
    monkeypatch.setattr(main, "process_unread", lambda service: calls.append(service) or 0)

    assert client.post("/pubsub", json={"message": {"data": "e30="}}).status_code == 204
    assert calls == ["service"]


def test_failed_emails_make_pubsub_retry(monkeypatch, client):
    monkeypatch.setattr(main, "process_unread", lambda service: 2)
    assert client.post("/pubsub").status_code == 500


def test_renew_watch_uses_configured_topic(monkeypatch, client):
    topics = []
    monkeypatch.setenv("PUBSUB_TOPIC", "projects/p/topics/gmail")
    monkeypatch.setattr(
        main.gmail_client,
        "watch_inbox",
        lambda service, topic: topics.append(topic) or {"expiration": "1", "historyId": "2"},
    )

    assert client.post("/renew-watch").status_code == 204
    assert topics == ["projects/p/topics/gmail"]
