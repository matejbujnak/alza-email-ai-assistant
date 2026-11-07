from types import SimpleNamespace

import pytest

from app import llm


def test_prompt_wraps_untrusted_input_and_omits_sender(make_email):
    prompt = llm.build_prompt(make_email(body="Ahoj\n\n", subject="  Otázka ", sender="secret.person@example.com"))

    assert "<email_subject>Otázka</email_subject>" in prompt
    assert "<email_body>\nAhoj\n</email_body>" in prompt
    assert "secret.person@example.com" not in prompt


def test_models_are_read_from_env_at_call_time(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "model-a")
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "model-b")
    assert llm.get_models() == ["model-a", "model-b"]


def test_duplicate_models_are_tried_once(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "same")
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "same")
    assert llm.get_models() == ["same"]


class FakeInteractions:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def create(self, *, model, **kwargs):
        self.calls.append({"model": model, **kwargs})
        result = self.responses[model]
        if isinstance(result, Exception):
            raise result
        return SimpleNamespace(output_text=result, status="completed")


@pytest.fixture
def fake_gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "primary")
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "fallback")

    def install(responses):
        interactions = FakeInteractions(responses)
        monkeypatch.setattr(llm, "get_client", lambda: SimpleNamespace(interactions=interactions))
        return interactions

    return install


def test_primary_model_reply_is_used(fake_gemini, make_email):
    fake = fake_gemini({"primary": "  Hi!  ", "fallback": "unused"})

    assert llm.generate_reply(make_email()) == "Hi!"
    assert [c["model"] for c in fake.calls] == ["primary"]
    assert fake.calls[0]["store"] is False


def test_falls_back_when_primary_fails(fake_gemini, make_email):
    fake = fake_gemini({"primary": RuntimeError("503 overloaded"), "fallback": "From fallback"})

    assert llm.generate_reply(make_email()) == "From fallback"
    assert [c["model"] for c in fake.calls] == ["primary", "fallback"]


def test_falls_back_when_primary_returns_no_text(fake_gemini, make_email):
    fake_gemini({"primary": None, "fallback": "From fallback"})
    assert llm.generate_reply(make_email()) == "From fallback"


def test_raises_when_all_models_fail(fake_gemini, make_email):
    fake_gemini({"primary": RuntimeError("down"), "fallback": RuntimeError("down")})
    with pytest.raises(RuntimeError, match="All Gemini models failed"):
        llm.generate_reply(make_email())
