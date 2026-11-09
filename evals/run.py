"""Evaluate retrieval and replies on a fixed set of test emails.

Each case runs several times, because the model's replies vary. A reply passes when it contains the
required strings and an LLM judge confirms it meets the case's criteria.

Usage:
    uv run python -m evals.run [--runs 3] [--case theft]
"""

import argparse
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from app import llm, rag
from app.gemini_client import get_client
from app.gmail_client import parse_email
from app.try_reply import build_message

CASES_FILE = Path(__file__).parent / "cases.json"
RESULTS_DIR = Path(__file__).parent / "results"
# The free tier allows 15 requests per minute and the deployed assistant shares the quota.
# Each run makes three requests (question split, reply, judge): about 10 a minute.
SECONDS_PER_RUN = 18
RETRY_DELAY_SECONDS = 40

JUDGE_INSTRUCTION = """\
You grade replies of a customer support assistant against a criterion.
Answer with PASS or FAIL on the first line, then one short sentence explaining why.
Judge only the criterion; extra correct information is fine.
"""


@dataclass
class CaseResult:
    id: str
    questions: list[str]
    retrieved: list[str]
    retrieval_ok: bool | None
    runs: list[dict] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(run["passed"] for run in self.runs)


def with_retry(call, attempts: int = 3):
    # Rate-limit errors aren't exposed as public classes (and generate_reply wraps them),
    # so any failure is retried after a pause long enough for the per-minute quota to reset.
    for attempt in range(attempts):
        try:
            return call()
        except Exception as exc:
            if attempt == attempts - 1:
                raise
            print(f"    retrying in {RETRY_DELAY_SECONDS} s: {str(exc)[:80]}")
            time.sleep(RETRY_DELAY_SECONDS)


def judge(case: dict, reply: str) -> tuple[bool, str]:
    prompt = f"<question>\n{case['body']}\n</question>\n<reply>\n{reply}\n</reply>\n<criterion>\n{case['criteria']}\n</criterion>"
    interaction = get_client().interactions.create(
        model=llm.get_models()[0], system_instruction=JUDGE_INSTRUCTION, input=prompt, store=False
    )
    verdict, _, reason = (interaction.output_text or "").strip().partition("\n")
    return verdict.strip().upper().startswith("PASS"), reason.strip()


def run_case(case: dict, runs: int) -> CaseResult:
    email = parse_email(build_message("customer@example.com", "", case["body"], []).as_bytes(), "eval", "eval")
    questions = llm.split_questions(email)
    retrieved = [k.chunk.heading for k in with_retry(lambda: rag.retrieve(questions))]
    expected = case["sections"]
    result = CaseResult(case["id"], questions, retrieved, all(s in retrieved for s in expected) if expected else None)

    for _ in range(runs):
        start = time.monotonic()
        reply = with_retry(lambda: llm.generate_reply(email))
        missing = [s for s in case.get("must_contain", []) if s not in reply]
        judged, reason = with_retry(lambda: judge(case, reply))
        result.runs.append(
            {"passed": judged and not missing, "missing": missing, "judge": reason, "reply": reply}
        )
        time.sleep(max(0.0, SECONDS_PER_RUN - (time.monotonic() - start)))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--case", action="append", help="run only this case id (repeatable)")
    args = parser.parse_args()

    load_dotenv()
    # Measure the primary model alone; a fallback would hide its failures.
    os.environ["GEMINI_FALLBACK_MODEL"] = llm.get_models()[0]

    cases = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    if args.case:
        cases = [c for c in cases if c["id"] in args.case]

    results = []
    for case in cases:
        result = run_case(case, args.runs)
        results.append(result)
        retrieval = {True: "ok", False: "MISSED", None: "-"}[result.retrieval_ok]
        print(f"{result.id:24} retrieval {retrieval:6} replies {result.passed}/{len(result.runs)}")
        for run in result.runs:
            if not run["passed"]:
                print(f"    FAIL: {run['judge']}" + (f" (missing {run['missing']})" if run["missing"] else ""))

    checked = [r for r in results if r.retrieval_ok is not None]
    total_runs = sum(len(r.runs) for r in results)
    print(
        f"\nRetrieval: {sum(r.retrieval_ok for r in checked)}/{len(checked)} cases found all expected sections"
        f"\nReplies:   {sum(r.passed for r in results)}/{total_runs} passed"
        f" ({100 * sum(r.passed for r in results) / total_runs:.0f} %), model {llm.get_models()[0]}"
    )

    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"{datetime.now():%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps([r.__dict__ for r in results], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Details: {out}")


if __name__ == "__main__":
    main()
