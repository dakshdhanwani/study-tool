"""
Standalone evaluation runner — can be run from the command line.

Usage:
    python evaluation/eval_runner.py
    python evaluation/eval_runner.py --report
    python evaluation/eval_runner.py --subset unanswerable
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
# Add the project root to the Python path
EVAL_PATH = PROJECT_ROOT / "evaluation" / "questions.json"
RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"


def run_evaluation(questions: list[dict]) -> list[dict]:
    from src.ingestion.indexer import load_index
    from src.retrieval.hybrid_search import hybrid_search
    from src.retrieval.reranker import get_reranker
    from src.generation.generator import generate_answer, configure_gemini

    configure_gemini()
    vector_store, bm25_index = load_index()
    reranker = get_reranker()
    results = []

    for i, q in enumerate(questions):
        print(f"  [{i+1}/{len(questions)}] Q{q['id']}: {q['question'][:60]}...", end=" ", flush=True)

        try:
            candidates = hybrid_search(q["question"], vector_store, bm25_index, top_k=12)
            chunks = reranker.rerank(q["question"], candidates, top_k=6)
            result = generate_answer(q["question"], chunks)

            q_type = q.get("type", "?")
            expected = q.get("expected_answer", "")
            source_docs = q.get("source_docs", [])

            answer_correct = False
            if q_type == "unanswerable":
                answer_correct = result.is_refusal
            elif expected and not result.is_refusal:
                exp_words = set(str(expected).lower().split())
                ans_words = set(result.answer.lower().split())
                overlap = len(exp_words & ans_words) / max(len(exp_words), 1)
                answer_correct = overlap >= 0.3

            cited_sources = {c.source_file.lower() for c in result.citations}
            expected_sources = {s.get("file", "").lower() for s in source_docs}
            citation_correct = expected_sources.issubset(cited_sources) if expected_sources else result.is_refusal

            status = "✅" if answer_correct else "❌"
            print(f"{status} (grounding: {result.grounding_score:.0%})")

            results.append({
                "id": q["id"], "type": q_type, "question": q["question"],
                "expected": expected,
                "answer": result.answer[:800] if not result.is_refusal else "[REFUSED]",
                "is_refusal": result.is_refusal,
                "refusal_reason": result.refusal_reason,
                "citations": [{"src": c.source_file, "page": c.page_number} for c in result.citations],
                "grounding_score": result.grounding_score,
                "answer_correct": answer_correct,
                "citation_correct": citation_correct,
                "source_docs": source_docs,
            })

        except Exception as exc:
            print(f"ERROR: {exc}")
            results.append({
                "id": q["id"], "type": q.get("type","?"), "question": q["question"],
                "error": str(exc), "answer_correct": False, "citation_correct": False,
                "is_refusal": False, "answer": f"[ERROR: {exc}]",
            })

    return results


def print_report(results: list[dict]) -> None:
    print("\n" + "="*60)
    print("EVALUATION REPORT")
    print("="*60)

    by_type: dict[str, list] = {}
    for r in results:
        by_type.setdefault(r.get("type", "?"), []).append(r)

    for q_type, type_results in sorted(by_type.items()):
        correct = sum(1 for r in type_results if r.get("answer_correct"))
        cit_correct = sum(1 for r in type_results if r.get("citation_correct"))
        n = len(type_results)
        print(f"\n{q_type.upper()} ({n} questions):")
        print(f"  Answer accuracy:   {correct}/{n} ({correct/n*100:.0f}%)")
        print(f"  Citation accuracy: {cit_correct}/{n} ({cit_correct/n*100:.0f}%)")

    print("\nOVERALL:")
    total_correct = sum(1 for r in results if r.get("answer_correct"))
    total_cit = sum(1 for r in results if r.get("citation_correct"))
    n = len(results)
    print(f"  Answer accuracy:   {total_correct}/{n} ({total_correct/n*100:.0f}%)")
    print(f"  Citation accuracy: {total_cit}/{n} ({total_cit/n*100:.0f}%)")
    refusals = sum(1 for r in results if r.get("is_refusal"))
    unansw = sum(1 for r in results if r.get("type") == "unanswerable")
    if unansw > 0:
        print(f"  Refusal rate:      {refusals}/{unansw} ({refusals/unansw*100:.0f}%) of unanswerable")
    print("="*60)


def main():
    parser = argparse.ArgumentParser(description="Run evaluation on the study workspace.")
    parser.add_argument("--subset", choices=["all", "single_doc", "multi_doc", "unanswerable"],
                        default="all")
    parser.add_argument("--report", action="store_true", help="Print summary report")
    args = parser.parse_args()

    if not EVAL_PATH.exists():
        print(f"ERROR: {EVAL_PATH} not found. Generate it from the Evaluation tab in the UI.")
        sys.exit(1)

    with open(EVAL_PATH, encoding="utf-8") as f:
        all_questions = json.load(f)

    if args.subset != "all":
        questions = [q for q in all_questions if q.get("type") == args.subset]
    else:
        questions = all_questions

    print(f"Running evaluation on {len(questions)} questions...")
    results = run_evaluation(questions)

    if args.report:
        print_report(results)

    # Save
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"eval_report_{ts}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nReport saved: {out_path}")


if __name__ == "__main__":
    main()


    