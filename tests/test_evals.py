import json

from app import rag
from evals.run import CASES_FILE


def test_eval_cases_reference_existing_sections():
    headings = {c.heading for c in rag.load_chunks()}
    cases = json.loads(CASES_FILE.read_text(encoding="utf-8"))

    assert len({c["id"] for c in cases}) == len(cases)
    for case in cases:
        assert set(case["sections"]) <= headings, case["id"]
