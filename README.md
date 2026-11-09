# Email AI Assistant

Proof of concept of an AI assistant that reads incoming emails and replies in the original thread using Gemini.

## Knowledge base

`knowledge/alzacare-plus/` contains the documents the assistant answers company-specific questions from. Each `##` section becomes one chunk, embedded with `gemini-embedding-2` into `knowledge/index.json`. After editing any document, rebuild the index with `uv run python -m app.rag build` (a test fails if the index is out of date). **AlzaCare+ is a fictional service created for this proof of concept**; its name, prices and terms are invented and do not describe any real Alza product or its actual terms.

## Development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync                      # install dependencies
cp .env.example .env         # then fill in your values
```

| Command                                                         | What it does                                                                   |
| --------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `uv run python -m app.processor`                                | Process unread emails in the bot inbox and reply                               |
| `uv run python -m app.try_reply --body "..." [--subject "..."] [--attach file]` | Print the bot's reply to a hand-written email; nothing is sent; `--attach` is repeatable |
| `uv run pytest`                                                 | Fast offline tests (no Gmail, no Gemini)                                       |
| `uv run pytest -m live -s`                                      | Behavioural tests against the real Gemini API; prints replies for human review |

### Configuration (`.env`)

| Variable                | Description                                                    |
| ----------------------- | -------------------------------------------------------------- |
| `GEMINI_API_KEY`        | Gemini API key from Google AI Studio                           |
| `GEMINI_MODEL`          | Primary model (default `gemini-3.5-flash-lite`)                |
| `GEMINI_FALLBACK_MODEL` | Used when the primary model fails (default `gemini-3.8-flash`) |
| `LOG_FILE`              | Optional path for a rotating log file, e.g. `logs/app.log`     |
| `GMAIL_TOKEN_FILE`      | Path to the Gmail OAuth token (default `token.json`)           |

The processor records handled emails in Firestore, so running it locally also needs Google Cloud credentials: `gcloud auth application-default login`. `try_reply` and the tests don't use Firestore.

Gmail access uses OAuth: put the OAuth client file at `credentials.json` and run `uv run python -m app.gmail_client login`, which opens a browser and stores the token in `token.json`. Both files are git-ignored. The token contains the client ID and secret, so `credentials.json` is only needed for logging in.

## Attachments

Supported attachments are sent to Gemini inline together with the email text:

- **Documents:** PDF, Word, Excel (first sheet only), PowerPoint, OpenDocument, CSV
- **Audio:** MP3, WAV, M4A, AAC, OGG, Opus, FLAC, AIFF, WebM
- **Images:** JPEG, PNG, WebP, GIF, HEIC/HEIF, BMP, TIFF
- **Video:** MP4, MOV, WebM, AVI, MPEG, WMV, FLV, 3GP (a `.webm` of unknown type is sent as video: Gemini also handles audio-only files that way, whereas a video sent as audio loses its picture)

Unsupported, empty or oversized files are skipped and listed in the prompt, so the reply can tell the customer which file couldn't be read. At most 10 attachments and 14 MB in total are processed (Gemini's 20 MB request limit including base64 overhead).

## Security

An auto-responder can be abused to send email to third parties (e.g. a forged `From`/`Reply-To` pointing at a victim). Current safeguards:

- **Sender authentication:** emails that fail Gmail's DMARC check, or pass neither SPF nor DKIM, are skipped. Only Gmail's own (topmost) `Authentication-Results` header is trusted.
- **No replies to automated senders:** own address, no-reply addresses (checked on the address the reply would go to), `Auto-Submitted`, bulk `Precedence` and mailing lists.
- **Loop prevention:** replies carry `Auto-Submitted: auto-replied` (RFC 3834).
- **Exactly one reply per email:** before processing, an instance claims the email in Firestore in a transaction, so concurrent instances or duplicate notifications don't answer twice. A claim abandoned by a crashed instance expires after 5 minutes; records are deleted after 30 days by a Firestore TTL policy.
- **Prompt-injection guard:** email subject and body are passed to the model as delimited, untrusted input.
- **Data minimization:** the sender's address is not sent to the LLM; Gemini interactions are not stored (`store=False`).

### Known limitations

- **Only the newest message in a thread is used:** the quoted previous message below a reply (`> ...` lines with their "On ... wrote:" line) is removed, so it doesn't distort knowledge retrieval. The bot therefore doesn't see earlier messages; planned: pass the thread history to the model separately and retrieve knowledge for the new message only. Outlook-style quotes without `>` are not detected yet.

- **No rate limiting yet:** a sender with a properly authenticated domain could still set `Reply-To` to a victim. Planned: per-recipient and global reply limits.
- **Attachments over 14 MB are skipped:** Gmail allows up to 25 MB. Larger files could be sent via the Gemini Files API, which however keeps uploaded files for up to 48 hours.
- **No output validation yet:** a prompt injection could make the model include arbitrary links. Planned: block links outside an allow-list of domains.
