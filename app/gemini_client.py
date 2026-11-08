from functools import cache

from google import genai
from google.genai import types


@cache
def get_client() -> genai.Client:
    # One attempt per model; falling back to another model is our retry strategy.
    # Worst case is len(models) * timeout, which keeps us under the 2-minute SLA
    # (SDK defaults retry 5 times with up to 60 s backoff).
    return genai.Client(
        http_options=types.HttpOptions(
            timeout=30_000,
            retry_options=types.HttpRetryOptions(attempts=1),
        )
    )
