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
        usage = SimpleNamespace(total_input_tokens=10, total_output_tokens=5)
        return SimpleNamespace(output_text=result, status="completed", usage=usage)


@pytest.fixture
def fake_gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "primary")
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "fallback")
    monkeypatch.setattr(llm, "split_questions", lambda email: ["question"])
    monkeypatch.setattr(llm.rag, "retrieve", lambda queries: [])

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


def test_input_contains_prompt_and_attachment_blocks(make_email):
    email = make_email(body="What's on the invoice?")
    email.mime.add_attachment(b"%PDF-1.7", maintype="application", subtype="pdf", filename="invoice.pdf")
    email.mime.add_attachment(b"PK", maintype="application", subtype="zip", filename="archive.zip")

    blocks = llm.build_input(email)

    assert blocks[0]["type"] == "text"
    assert "<attachments>\n- invoice.pdf (application/pdf)\n</attachments>" in blocks[0]["text"]
    assert "- archive.zip: unsupported file type (application/zip)" in blocks[0]["text"]
    assert blocks[1] == {"type": "document", "data": "JVBERi0xLjc=", "mime_type": "application/pdf"}
    assert len(blocks) == 2


def test_prompt_has_no_attachment_sections_without_files(make_email):
    prompt = llm.build_prompt(make_email())
    assert "<attachments>" not in prompt and "<skipped_attachments>" not in prompt


def test_split_questions_returns_model_list(monkeypatch, make_email):
    reply = SimpleNamespace(output_text='{"questions": ["Cena Premium?", " ", "Kryje krádež?"]}')
    calls = []
    interactions = SimpleNamespace(create=lambda **kwargs: calls.append(kwargs) or reply)
    monkeypatch.setattr(llm, "get_client", lambda: SimpleNamespace(interactions=interactions))

    assert llm.split_questions(make_email(body="Cena Premium? Kryje krádež?")) == ["Cena Premium?", "Kryje krádež?"]
    assert calls[0]["response_format"]["mime_type"] == "application/json"


def test_split_questions_falls_back_to_whole_email(monkeypatch, make_email):
    def failing_create(**kwargs):
        raise RuntimeError("429")

    monkeypatch.setattr(llm, "get_client", lambda: SimpleNamespace(interactions=SimpleNamespace(create=failing_create)))
    assert llm.split_questions(make_email(body="Ahoj", subject="Otázka")) == ["Otázka\nAhoj"]
