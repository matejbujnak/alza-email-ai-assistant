from email.message import EmailMessage

import pytest

from app import attachments as att
from app.attachments import extract_attachments, normalize_mime_type


def message_with(*files: tuple[bytes, str, str]) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = "jane@example.com"
    msg.set_content("See attached.")
    msg.add_alternative("<p>See attached.</p>", subtype="html")
    for data, mime_type, filename in files:
        maintype, subtype = mime_type.split("/")
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
    return msg


def test_extracts_document_audio_and_image():
    msg = message_with(
        (b"%PDF-1.7", "application/pdf", "invoice.pdf"),
        (b"ID3audio", "audio/mpeg", "voice.mp3"),
        (b"\x89PNGimg", "image/png", "photo.png"),
    )

    found, skipped = extract_attachments(msg)

    assert [(a.filename, a.kind, a.mime_type) for a in found] == [
        ("invoice.pdf", "document", "application/pdf"),
        ("voice.mp3", "audio", "audio/mpeg"),
        ("photo.png", "image", "image/png"),
    ]
    assert found[0].data == b"%PDF-1.7"
    assert skipped == []


def test_text_bodies_are_not_attachments():
    found, skipped = extract_attachments(message_with())
    assert found == [] and skipped == []


@pytest.mark.parametrize(
    ("content_type", "filename", "expected"),
    [
        ("audio/x-wav", "a.wav", "audio/wav"),
        ("image/jpg", "a.jpg", "image/jpeg"),
        ("application/octet-stream", "report.pdf", "application/pdf"),
        ("application/octet-stream", "memo.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("application/zip", "archive.zip", "application/zip"),
    ],
)
def test_normalize_mime_type(content_type, filename, expected):
    assert normalize_mime_type(content_type, filename) == expected


def test_unsupported_and_empty_files_are_skipped_with_reason():
    msg = message_with((b"PK", "application/zip", "archive.zip"), (b"", "image/png", "empty.png"))

    found, skipped = extract_attachments(msg)

    assert found == []
    assert [(s.filename, s.reason) for s in skipped] == [
        ("archive.zip", "unsupported file type (application/zip)"),
        ("empty.png", "empty file"),
    ]


def test_files_over_budget_are_skipped(monkeypatch):
    monkeypatch.setattr(att, "INLINE_BUDGET_BYTES", 10)
    msg = message_with((b"12345678", "image/png", "small.png"), (b"12345678", "image/png", "big.png"))

    found, skipped = extract_attachments(msg)

    assert [a.filename for a in found] == ["small.png"]
    assert [(s.filename, s.reason) for s in skipped] == [("big.png", "file too large")]


def test_attachment_count_is_limited(monkeypatch):
    monkeypatch.setattr(att, "MAX_ATTACHMENTS", 1)
    msg = message_with((b"a", "image/png", "1.png"), (b"b", "image/png", "2.png"))

    found, skipped = extract_attachments(msg)

    assert [a.filename for a in found] == ["1.png"]
    assert skipped[0].reason == "too many attachments (max 1)"


def test_inline_pasted_image_is_extracted():
    # Gmail puts images pasted into the text in a multipart/related part next to the HTML body.
    msg = EmailMessage()
    msg.set_content("Screenshot below")
    msg.add_alternative('<p>Screenshot below</p><img src="cid:shot">', subtype="html")
    msg.get_payload()[1].add_related(b"\x89PNGshot", maintype="image", subtype="png", cid="<shot>")

    found, _ = extract_attachments(msg)

    assert [(a.kind, a.data) for a in found] == [("image", b"\x89PNGshot")]
