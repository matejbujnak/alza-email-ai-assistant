"""Retrieval over the Markdown knowledge base.

Build the index after changing any document in knowledge/:
    uv run python -m app.rag build
"""

import hashlib
import json
import logging
import sys
from dataclasses import asdict, dataclass
from functools import cache
from pathlib import Path

from google.genai import types

from app.gemini_client import get_client

logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"
INDEX_FILE = KNOWLEDGE_DIR / "index.json"

EMBEDDING_MODEL = "gemini-embedding-2"
DIMENSIONS = 768
TOP_K = 4
# Calibrated on sample queries: clearly off-topic questions score below ~0.6, relevant ones
# above ~0.68. Borderline queries pass through; the prompt decides whether the context answers them.
MIN_SCORE = 0.6


@dataclass(frozen=True)
class Chunk:
    id: str
    source: str
    title: str
    heading: str
    text: str


@dataclass(frozen=True)
class ScoredChunk:
    chunk: Chunk
    score: float


def split_markdown(text: str, source: str) -> list[Chunk]:
    """One chunk per `##` section, so each chunk covers a single topic."""
    title = ""
    chunks: list[Chunk] = []
    heading, lines = "", []

    def flush() -> None:
        body = "\n".join(lines).strip()
        if heading and body:
            chunks.append(Chunk(f"{source}#{len(chunks) + 1}", source, title, heading, body))

    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("## "):
            flush()
            heading, lines = line[3:].strip(), []
        else:
            lines.append(line)
    flush()
    return chunks


def load_chunks(knowledge_dir: Path = KNOWLEDGE_DIR) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(knowledge_dir.rglob("*.md")):
        chunks += split_markdown(path.read_text(encoding="utf-8"), path.relative_to(knowledge_dir).as_posix())
    return chunks


def document_text(chunk: Chunk) -> str:
    # gemini-embedding-2 ignores task_type; the task is expressed as a text prefix instead.
    return f"title: {chunk.title} - {chunk.heading} | text: {chunk.text}"


def content_hash(chunks: list[Chunk]) -> str:
    # Hash the exact embedded texts, so changing the prefix also marks the index as stale.
    payload = json.dumps(
        [EMBEDDING_MODEL, DIMENSIONS, [(c.id, document_text(c)) for c in chunks]], ensure_ascii=False
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _embed(texts: list[str]) -> list[list[float]]:
    # gemini-embedding-2 merges a plain list into one vector; one Content per text keeps them separate.
    response = get_client().models.embed_content(
        model=EMBEDDING_MODEL,
        contents=[types.Content(parts=[types.Part(text=t)]) for t in texts],
        config=types.EmbedContentConfig(output_dimensionality=DIMENSIONS),
    )
    return [e.values for e in response.embeddings]


def embed_documents(chunks: list[Chunk]) -> list[list[float]]:
    return _embed([document_text(c) for c in chunks])


def embed_query(query: str) -> list[float]:
    return _embed([f"task: search result | query: {query}"])[0]


def dump_index(index: dict) -> str:
    # Indent the structure but keep each vector on one line, so the file stays readable and small.
    placeholders = [f"__embedding_{i}__" for i in range(len(index["chunks"]))]
    chunks = [{**c, "embedding": p} for c, p in zip(index["chunks"], placeholders, strict=True)]
    text = json.dumps({**index, "chunks": chunks}, ensure_ascii=False, indent=2)
    for chunk, placeholder in zip(index["chunks"], placeholders, strict=True):
        text = text.replace(f'"{placeholder}"', json.dumps(chunk["embedding"]))
    return text + "\n"


def build_index() -> None:
    chunks = load_chunks()
    vectors = embed_documents(chunks)
    index = {
        "model": EMBEDDING_MODEL,
        "dimensions": DIMENSIONS,
        "content_hash": content_hash(chunks),
        "chunks": [{**asdict(c), "embedding": v} for c, v in zip(chunks, vectors, strict=True)],
    }
    INDEX_FILE.write_text(dump_index(index), encoding="utf-8")
    logger.info("Indexed %d chunks into %s", len(chunks), INDEX_FILE)


@cache
def load_index() -> tuple[list[Chunk], list[list[float]]]:
    index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    chunks = [Chunk(**{k: v for k, v in c.items() if k != "embedding"}) for c in index["chunks"]]
    if index["content_hash"] != content_hash(load_chunks()):
        raise RuntimeError("Knowledge index is out of date, run: uv run python -m app.rag build")
    return chunks, [c["embedding"] for c in index["chunks"]]


def retrieve(query: str, top_k: int = TOP_K, min_score: float = MIN_SCORE) -> list[ScoredChunk]:
    chunks, vectors = load_index()
    query_vector = embed_query(query)
    # Embeddings are unit-normalized, so the dot product equals cosine similarity.
    scored = [ScoredChunk(c, sum(a * b for a, b in zip(query_vector, v))) for c, v in zip(chunks, vectors)]
    scored.sort(key=lambda s: s.score, reverse=True)
    return [s for s in scored[:top_k] if s.score >= min_score]


if __name__ == "__main__":
    from dotenv import load_dotenv

    from app.logging_config import setup_logging

    load_dotenv()
    setup_logging()
    if sys.argv[1:] == ["build"]:
        build_index()
    else:
        sys.exit(__doc__)
