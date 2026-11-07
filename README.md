# Email AI Assistant

Proof of concept of an AI assistant that reads incoming emails and replies in the
original thread using Gemini.

## Development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync                      # install dependencies
cp .env.example .env         # then fill in your values
```

| Command                                                         | What it does                                                                   |
| --------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `uv run python -m app.processor`                                | Process unread emails in the bot inbox and reply                               |
| `uv run python -m app.try_reply --body "..." [--subject "..."]` | Print the bot's reply to a hand-written email; nothing is sent                 |
| `uv run pytest`                                                 | Fast offline tests (no Gmail, no Gemini)                                       |
| `uv run pytest -m live -s`                                      | Behavioural tests against the real Gemini API; prints replies for human review |

### Configuration (`.env`)

| Variable                | Description                                                    |
| ----------------------- | -------------------------------------------------------------- |
| `GEMINI_API_KEY`        | Gemini API key from Google AI Studio                           |
| `GEMINI_MODEL`          | Primary model (default `gemini-3.5-flash-lite`)                |
| `GEMINI_FALLBACK_MODEL` | Used when the primary model fails (default `gemini-3.8-flash`) |
| `LOG_FILE`              | Optional path for a rotating log file, e.g. `logs/app.log`     |

Gmail access uses OAuth: put the OAuth client file at `credentials.json`; the first run
opens a browser and stores the token in `token.json`. Both files are git-ignored.
