import json

from app import llm, rag
from app.rag import Chunk, ScoredChunk, split_markdown

DOC = """# AlzaCare+ - test

Intro text before the first section is ignored.

## Cenník

Štandard 29 €.

## Prázdna sekcia

## Zrušenie

Do 14 dní vrátime celú sumu.
"""


def test_split_markdown_creates_one_chunk_per_section():
    chunks = split_markdown(DOC, "test.md")

    assert [(c.heading, c.text) for c in chunks] == [
        ("Cenník", "Štandard 29 €."),
        ("Zrušenie", "Do 14 dní vrátime celú sumu."),
    ]
    assert {c.title for c in chunks} == {"AlzaCare+ - test"}
    assert [c.id for c in chunks] == ["test.md#1", "test.md#2"]


def test_index_is_up_to_date_with_knowledge_documents():
    index = json.loads(rag.INDEX_FILE.read_text(encoding="utf-8"))
    assert index["content_hash"] == rag.content_hash(rag.load_chunks()), (
        "Knowledge documents changed: run `uv run python -m app.rag build`"
    )
    assert index["model"] == rag.EMBEDDING_MODEL
    assert all(len(c["embedding"]) == rag.DIMENSIONS for c in index["chunks"])


def chunk(heading: str) -> Chunk:
    return Chunk(id=heading, source="doc.md", title="Doc", heading=heading, text=f"{heading} text")


def test_retrieve_ranks_by_similarity_and_applies_threshold(monkeypatch):
    chunks = [chunk("far"), chunk("best"), chunk("close"), chunk("off-topic")]
    vectors = [[0.6, 0.8], [1.0, 0.0], [0.8, 0.6], [0.0, 1.0]]
    monkeypatch.setattr(rag, "load_index", lambda: (chunks, vectors))
    monkeypatch.setattr(rag, "embed_query", lambda query: [1.0, 0.0])

    results = rag.retrieve("question", top_k=3, min_score=0.7)

    assert [(r.chunk.heading, round(r.score, 2)) for r in results] == [("best", 1.0), ("close", 0.8)]


def test_prompt_contains_knowledge_excerpts(make_email):
    knowledge = [ScoredChunk(Chunk("x", "alzacare-plus/ceny.md", "Doc", "Cenník", "Premium 159 €"), 0.8)]
    prompt = llm.build_prompt(make_email(), knowledge=knowledge)

    assert '<excerpt source="alzacare-plus/ceny.md" section="Cenník">\nPremium 159 €\n</excerpt>' in prompt
    assert prompt.index("<knowledge>") < prompt.index("<email_body>")


def test_prompt_states_when_no_knowledge_was_found(make_email):
    assert "<knowledge>\n(no relevant documents found)\n</knowledge>" in llm.build_prompt(make_email())


def test_retrieval_failure_degrades_to_no_knowledge(monkeypatch, make_email):
    def failing_retrieve(query):
        raise RuntimeError("embedding API down")

    monkeypatch.setattr(llm.rag, "retrieve", failing_retrieve)
    assert llm.find_knowledge(make_email()) == []
