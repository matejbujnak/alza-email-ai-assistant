import mimetypes
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Literal

Kind = Literal["document", "audio", "image", "video"]

# MIME types accepted by the Gemini Interactions API (google-genai 3.0).
SUPPORTED_TYPES: dict[str, Kind] = {
    "application/pdf": "document",
    "application/msword": "document",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "document",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.template": "document",
    "application/vnd.ms-excel": "document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "document",
    "application/vnd.ms-powerpoint": "document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "document",
    "application/vnd.oasis.opendocument.text": "document",
    "application/vnd.oasis.opendocument.spreadsheet": "document",
    "application/vnd.oasis.opendocument.presentation": "document",
    "text/csv": "document",
    "audio/mp3": "audio",
    "audio/mpeg": "audio",
    "audio/wav": "audio",
    "audio/m4a": "audio",
    "audio/aac": "audio",
    "audio/ogg": "audio",
    "audio/opus": "audio",
    "audio/flac": "audio",
    "audio/aiff": "audio",
    "audio/webm": "audio",
    "audio/l16": "audio",
    "audio/alaw": "audio",
    "audio/mulaw": "audio",
    "image/jpeg": "image",
    "image/png": "image",
    "image/webp": "image",
    "image/gif": "image",
    "image/heic": "image",
    "image/heif": "image",
    "image/bmp": "image",
    "image/tiff": "image",
    "video/mp4": "video",
    "video/mpeg": "video",
    "video/mpg": "video",
    "video/mov": "video",
    "video/avi": "video",
    "video/x-flv": "video",
    "video/webm": "video",
    "video/wmv": "video",
    "video/3gpp": "video",
}

# Non-standard names that mail clients and phones commonly send.
TYPE_ALIASES = {
    "audio/x-wav": "audio/wav",
    "audio/wave": "audio/wav",
    "audio/vnd.wave": "audio/wav",
    "audio/x-m4a": "audio/m4a",
    "audio/mp4": "audio/m4a",
    "audio/x-mp3": "audio/mp3",
    "audio/x-flac": "audio/flac",
    "audio/x-aiff": "audio/aiff",
    "image/jpg": "image/jpeg",
    "image/pjpeg": "image/jpeg",
    "video/quicktime": "video/mov",
    "video/x-msvideo": "video/avi",
    "video/vnd.avi": "video/avi",
    "video/x-ms-wmv": "video/wmv",
    # 3GP containers may hold audio only; Gemini handles audio-only files sent as video.
    "audio/3gpp": "video/3gpp",
}

# Extensions Python's mimetypes doesn't know. Ambiguous containers (.webm) resolve to
# video on purpose: Gemini processes audio-only files sent as video, but drops the
# picture of a video sent as audio.
EXTENSION_TYPES = {
    ".dotx": "application/vnd.openxmlformats-officedocument.wordprocessingml.template",
    ".flv": "video/x-flv",
}

# Gemini caps a request at 20 MB including base64 overhead (+33 %), so raw bytes must stay well below.
INLINE_BUDGET_BYTES = 14 * 1024 * 1024
MAX_ATTACHMENTS = 10


@dataclass(frozen=True)
class Attachment:
    filename: str
    mime_type: str
    kind: Kind
    data: bytes


@dataclass(frozen=True)
class SkippedAttachment:
    filename: str
    reason: str


def normalize_mime_type(content_type: str, filename: str) -> str:
    mime_type = TYPE_ALIASES.get(content_type.lower(), content_type.lower())
    if mime_type in SUPPORTED_TYPES:
        return mime_type
    # Fall back to the extension, e.g. for generic application/octet-stream.
    extension = Path(filename).suffix.lower()
    if extension in EXTENSION_TYPES:
        return EXTENSION_TYPES[extension]
    guessed, _ = mimetypes.guess_type(filename)
    if guessed:
        guessed = TYPE_ALIASES.get(guessed, guessed)
        if guessed in SUPPORTED_TYPES:
            return guessed
    return mime_type


def _file_parts(mime: EmailMessage):
    body_parts = {id(part) for part in (mime.get_body(("plain",)), mime.get_body(("html",))) if part}
    for part in mime.walk():
        if part.is_multipart() or id(part) in body_parts:
            continue
        # Alternative text bodies without a filename are not attachments.
        if part.get_content_maintype() == "text" and not part.get_filename():
            continue
        yield part


def extract_attachments(mime: EmailMessage) -> tuple[list[Attachment], list[SkippedAttachment]]:
    attachments: list[Attachment] = []
    skipped: list[SkippedAttachment] = []
    budget = INLINE_BUDGET_BYTES

    for part in _file_parts(mime):
        filename = part.get_filename() or "unnamed"
        mime_type = normalize_mime_type(part.get_content_type(), filename)

        if (kind := SUPPORTED_TYPES.get(mime_type)) is None:
            skipped.append(SkippedAttachment(filename, f"unsupported file type ({mime_type})"))
            continue

        content = part.get_content()
        data = content.encode() if isinstance(content, str) else content

        if not data:
            skipped.append(SkippedAttachment(filename, "empty file"))
        elif len(attachments) >= MAX_ATTACHMENTS:
            skipped.append(SkippedAttachment(filename, f"too many attachments (max {MAX_ATTACHMENTS})"))
        elif len(data) > budget:
            skipped.append(SkippedAttachment(filename, "file too large"))
        else:
            attachments.append(Attachment(filename, mime_type, kind, data))
            budget -= len(data)

    return attachments, skipped
