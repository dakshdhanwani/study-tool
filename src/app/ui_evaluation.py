"""
Evaluation tab: run the 30-question test set and report metrics.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def render_evaluation_tab():
    st.header("📊 Evaluation Dashboard")
    st.markdown(
        "Run the **30-question evaluation** (10 single-doc, 10 multi-doc, 10 unanswerable) "
        "and report answer + citation + refusal accuracy."
    )

    eval_path = PROJECT_ROOT / "evaluation" / "questions.json"
    results_dir = PROJECT_ROOT / "evaluation" / "results"

    # ── Load questions ─────────────────────────────────────────────────────────
    if not eval_path.exists():
        st.warning("questions.json not found. It will be auto-generated.")
        if st.button("Generate evaluation questions"):
            _generate_questions(eval_path)
            st.rerun()
        return

    with open(eval_path, encoding="utf-8") as f:
        questions = json.load(f)

    single_doc = [q for q in questions if q.get("type") == "single_doc"]
    multi_doc   = [q for q in questions if q.get("type") == "multi_doc"]
    unansw      = [q for q in questions if q.get("type") == "unanswerable"]

    col1, col2, col3 = st.columns(3)
    col1.metric("Single-doc questions", len(single_doc))
    col2.metric("Multi-doc questions", len(multi_doc))
    col3.metric("Unanswerable questions", len(unansw))

    # ── Browse questions ───────────────────────────────────────────────────────
    with st.expander("📋 Browse all questions"):
        for q_type, q_list in [
            ("🔵 Single-doc", single_doc),
            ("🟣 Multi-doc", multi_doc),
            ("🔴 Unanswerable", unansw),
        ]:
            st.markdown(f"#### {q_type}")
            for q in q_list:
                srcs = ", ".join(
                    f"{s.get('file','?')}:p{s.get('page','?')}"
                    for s in q.get("source_docs", [])
                )
                expected = q.get("expected_answer", "—") or "—"
                st.markdown(
                    f"**Q{q['id']}:** {q['question']}  \n"
                    f"*Expected:* {expected[:80]}{'…' if len(str(expected))>80 else ''}  \n"
                    f"*Sources:* `{srcs or 'none'}`"
                )
            st.divider()

    # ── Run evaluation ─────────────────────────────────────────────────────────
    st.subheader("Run Evaluation")

    col_run1, col_run2 = st.columns(2)
    with col_run1:
        run_subset = st.selectbox(
            "Run subset:",
            ["All 30 questions", "Single-doc only (10)", "Multi-doc only (10)", "Unanswerable only (10)"],
        )
    with col_run2:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        run_eval = st.button("▶️ Run Evaluation", type="primary")

    if run_eval:
        subset_map = {
            "All 30 questions": questions,
            "Single-doc only (10)": single_doc,
            "Multi-doc only (10)": multi_doc,
            "Unanswerable only (10)": unansw,
        }
        eval_questions = subset_map[run_subset]

        with st.spinner(f"Running evaluation on {len(eval_questions)} questions..."):
            results = _run_eval(eval_questions)

        if results:
            _show_results(results, results_dir)

    # ── Past results ───────────────────────────────────────────────────────────
    if results_dir.exists():
        past_reports = sorted(results_dir.glob("eval_report_*.json"), reverse=True)
        if past_reports:
            st.divider()
            st.subheader("Past Evaluation Reports")
            chosen = st.selectbox("Load report:", [p.name for p in past_reports])
            if chosen:
                with open(results_dir / chosen, encoding="utf-8") as f:
                    past_data = json.load(f)
                _show_results(past_data, results_dir, save=False)


def _run_eval(questions: list[dict]) -> list[dict] | None:
    """Run evaluation on a list of questions. Returns list of result dicts."""
    try:
        from src.retrieval.vector_store import get_vector_store
        vs = get_vector_store()
        if vs.collection_size() == 0:
            st.error("No documents ingested. Go to Materials tab first.")
            return None

        from src.ingestion.indexer import load_index
        from src.retrieval.hybrid_search import hybrid_search
        from src.retrieval.reranker import get_reranker
        from src.generation.generator import generate_answer, configure_gemini

        configure_gemini()
        vector_store, bm25_index = load_index()
        reranker = get_reranker()

        results = []
        progress = st.progress(0, text="Starting evaluation...")

        for i, q in enumerate(questions):
            progress.progress((i + 1) / len(questions), text=f"Q{q['id']}: {q['question'][:50]}...")

            try:
                candidates = hybrid_search(q["question"], vector_store, bm25_index, top_k=12)
                chunks = reranker.rerank(q["question"], candidates, top_k=6)
                result = generate_answer(q["question"], chunks)

                expected = q.get("expected_answer")
                source_docs = q.get("source_docs", [])
                q_type = q.get("type", "unknown")

                # Evaluate answer correctness (simple heuristic — keyword overlap)
                answer_correct = False
                if q_type == "unanswerable":
                    answer_correct = result.is_refusal
                elif expected and not result.is_refusal:
                    exp_words = set(str(expected).lower().split())
                    ans_words = set(result.answer.lower().split())
                    overlap = len(exp_words & ans_words) / max(len(exp_words), 1)
                    answer_correct = overlap >= 0.3  # Conservative threshold

                # Evaluate citation correctness
                cited_sources = set()
                for c in result.citations:
                    cited_sources.add(c.source_file.lower())
                expected_sources = set(s.get("file", "").lower() for s in source_docs)
                citation_correct = (
                    expected_sources.issubset(cited_sources)
                    if expected_sources else result.is_refusal
                )

                results.append({
                    "id": q["id"],
                    "question": q["question"],
                    "type": q_type,
                    "expected": expected,
                    "answer": result.answer[:500] if not result.is_refusal else "[REFUSED]",
                    "is_refusal": result.is_refusal,
                    "refusal_reason": result.refusal_reason,
                    "citations": [{"src": c.source_file, "page": c.page_number} for c in result.citations],
                    "grounding_score": result.grounding_score,
                    "answer_correct": answer_correct,
                    "citation_correct": citation_correct,
                    "source_docs": source_docs,
                })

            except Exception as exc:
                results.append({
                    "id": q["id"], "question": q["question"], "type": q.get("type", "?"),
                    "error": str(exc), "answer_correct": False, "citation_correct": False,
                    "is_refusal": False, "answer": f"[ERROR: {exc}]",
                })

        progress.empty()
        return results

    except Exception as exc:
        st.error(f"Evaluation setup failed: {exc}")
        import traceback
        st.code(traceback.format_exc())
        return None


def _show_results(results: list[dict], results_dir: Path, save: bool = True) -> None:
    """Render evaluation results and optionally save to disk."""
    import datetime

    if not results:
        st.warning("No results to display.")
        return

    # Compute metrics
    by_type: dict[str, list] = {}
    for r in results:
        by_type.setdefault(r.get("type", "?"), []).append(r)

    st.subheader("📊 Results")
    st.divider()

    for q_type, type_results in sorted(by_type.items()):
        correct = sum(1 for r in type_results if r.get("answer_correct"))
        cit_correct = sum(1 for r in type_results if r.get("citation_correct"))
        total = len(type_results)

        type_label = {
            "single_doc": "🔵 Single-doc", "multi_doc": "🟣 Multi-doc",
            "unanswerable": "🔴 Unanswerable"
        }.get(q_type, q_type)

        st.markdown(f"#### {type_label}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Answer accuracy", f"{correct}/{total}", f"{correct/total*100:.0f}%")
        c2.metric("Citation accuracy", f"{cit_correct}/{total}", f"{cit_correct/total*100:.0f}%")
        avg_grounding = sum(r.get("grounding_score", 1.0) for r in type_results) / total
        c3.metric("Avg grounding score", f"{avg_grounding:.0%}")

        with st.expander("Per-question results"):
            for r in type_results:
                icon = "✅" if r.get("answer_correct") else "❌"
                cit_icon = "✅" if r.get("citation_correct") else "❌"
                refusal = " 🚫 REFUSED" if r.get("is_refusal") else ""

                citations = ", ".join(
                    f"[{c['src']}:{c['page']}]"
                    for c in r.get("citations", [])
                )

                st.markdown(
                    f"**Q{r['id']}** {icon} Answer | "
                    f"{cit_icon} Citations{refusal}  \n"
                    f"*{r['question'][:80]}*  \n"
                    f"Answer: {str(r.get('answer', ''))[:150]}  \n"
                    f"Citations: {citations}"
                )

                st.divider()

    # Overall summary
    st.subheader("Overall Summary")
    total_correct = sum(1 for r in results if r.get("answer_correct"))
    total_cit = sum(1 for r in results if r.get("citation_correct"))
    n = len(results)

    c1, c2, c3 = st.columns(3)
    c1.metric("Overall answer accuracy", f"{total_correct}/{n}", f"{total_correct/n*100:.0f}%")
    c2.metric("Overall citation accuracy", f"{total_cit}/{n}", f"{total_cit/n*100:.0f}%")
    refusals = sum(1 for r in results if r.get("is_refusal"))
    unansw_total = sum(1 for r in results if r.get("type") == "unanswerable")
    if unansw_total > 0:
        c3.metric("Refusal rate", f"{refusals}/{n}", f"{refusals/unansw_total*100:.0f}% of unanswerable")

    # Save report
    if save:
        results_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = results_dir / f"eval_report_{ts}.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        st.success(f"Report saved to `{report_path.name}`")

        # Markdown report
        md_path = results_dir / f"eval_report_{ts}.md"
        _write_markdown_report(results, md_path)
        with open(md_path, encoding="utf-8") as f:
            st.download_button("⬇️ Download Markdown Report", f.read(),
                               file_name=md_path.name, mime="text/markdown")


def _write_markdown_report(results: list[dict], path: Path) -> None:
    lines = ["# Evaluation Report\n"]
    total_correct = sum(1 for r in results if r.get("answer_correct"))
    total_cit = sum(1 for r in results if r.get("citation_correct"))
    n = len(results)
    lines.append(f"**Overall accuracy:** {total_correct}/{n} ({total_correct/n*100:.0f}%)  ")
    lines.append(f"**Citation accuracy:** {total_cit}/{n} ({total_cit/n*100:.0f}%)\n")
    lines.append("---\n")
    for r in results:
        lines.append(f"### Q{r['id']} ({r.get('type','?')})")
        lines.append(f"**Q:** {r['question']}")
        lines.append(f"**Answer correct:** {'✅' if r.get('answer_correct') else '❌'}")
        lines.append(f"**Citation correct:** {'✅' if r.get('citation_correct') else '❌'}")
        if r.get("is_refusal"):
            lines.append(f"**REFUSED:** {r.get('refusal_reason','')}")
        lines.append(f"**Answer:** {r.get('answer','')[:300]}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _generate_questions(eval_path: Path) -> None:
    """Create the standard 30-question evaluation set."""
    questions = [
        # Single-doc (10)
        {"id": 1, "type": "single_doc", "question": "What is the time complexity of Dijkstra's algorithm with a binary heap?", "expected_answer": "O((V + E) log V)", "source_docs": [{"file": "slides_01_overview.pdf", "page": 7}]},
        {"id": 2, "type": "single_doc", "question": "What are the three cases of the Master Theorem?", "expected_answer": "Case 1: leaves dominate, Case 2: equal, Case 3: root dominates", "source_docs": [{"file": "slides_01_overview.pdf", "page": 3}]},
        {"id": 3, "type": "single_doc", "question": "What is the time complexity of Merge Sort in all cases?", "expected_answer": "O(n log n)", "source_docs": [{"file": "lecture_03_sorting.pdf", "page": 3}]},
        {"id": 4, "type": "single_doc", "question": "What data structure does BFS use?", "expected_answer": "Queue", "source_docs": [{"file": "slides_01_overview.pdf", "page": 5}]},
        {"id": 5, "type": "single_doc", "question": "What is the worst-case time complexity of Quicksort?", "expected_answer": "O(n²)", "source_docs": [{"file": "lecture_03_sorting.pdf", "page": 4}]},
        {"id": 6, "type": "single_doc", "question": "What is the heap property of a max-heap?", "expected_answer": "parent >= children", "source_docs": [{"file": "lecture_02_trees.pdf", "page": 3}]},
        {"id": 7, "type": "single_doc", "question": "What is a Trie used for?", "expected_answer": "Storing strings / autocomplete / prefix search", "source_docs": [{"file": "lecture_02_trees.pdf", "page": 6}]},
        {"id": 8, "type": "single_doc", "question": "What does LIFO stand for and which data structure uses it?", "expected_answer": "Last In First Out — Stack", "source_docs": [{"file": "lecture_01_basics.pdf", "page": 4}]},
        {"id": 9, "type": "single_doc", "question": "What is the amortized cost of push in a dynamic array?", "expected_answer": "O(1) amortized", "source_docs": [{"file": "lecture_01_basics.pdf", "page": 2}]},
        {"id": 10, "type": "single_doc", "question": "How does Kruskal's algorithm find the MST?", "expected_answer": "Sort edges by weight, add edge if no cycle using Union-Find", "source_docs": [{"file": "slides_02_advanced.pdf", "page": 2}]},

        # Multi-doc (10)
        {"id": 11, "type": "multi_doc", "question": "Compare the time complexity of Dijkstra's and Bellman-Ford algorithms.", "expected_answer": "Dijkstra O((V+E)logV), Bellman-Ford O(VE)", "source_docs": [{"file": "slides_01_overview.pdf", "page": 7}, {"file": "slides_01_overview.pdf", "page": 8}]},
        {"id": 12, "type": "multi_doc", "question": "How do the handwritten notes describe BFS compared to the slides?", "expected_answer": "Both note queue usage and O(V+E) time", "source_docs": [{"file": "handwritten_hard.png", "page": 1}, {"file": "slides_01_overview.pdf", "page": 5}]},
        {"id": 13, "type": "multi_doc", "question": "How does the recursion tree method relate to the Master Theorem?", "expected_answer": "Recursion tree sums level costs to derive the Master Theorem cases", "source_docs": [{"file": "study_notes.md", "page": 2}, {"file": "slides_01_overview.pdf", "page": 3}]},
        {"id": 14, "type": "multi_doc", "question": "Compare Merge Sort and Quicksort in terms of stability and space complexity.", "expected_answer": "Merge Sort: stable O(n) space; Quicksort: unstable O(log n) space", "source_docs": [{"file": "lecture_03_sorting.pdf", "page": 3}, {"file": "lecture_03_sorting.pdf", "page": 4}]},
        {"id": 15, "type": "multi_doc", "question": "What does the study notes say about when greedy algorithms fail, and does this match the slides?", "expected_answer": "Both say greedy fails on 0-1 Knapsack; use DP instead", "source_docs": [{"file": "study_notes.md", "page": 5}, {"file": "slides_01_overview.pdf", "page": 12}]},
        {"id": 16, "type": "multi_doc", "question": "How is the LCS problem defined in the notes and what recurrence does it use?", "expected_answer": "Longest Common Subsequence; dp[i][j] = dp[i-1][j-1]+1 if match, else max(dp[i-1][j], dp[i][j-1])", "source_docs": [{"file": "study_notes.md", "page": 3}, {"file": "slides_01_overview.pdf", "page": 10}]},
        {"id": 17, "type": "multi_doc", "question": "What does the handwritten note say about which algorithm to use for negative edge weights?", "expected_answer": "Bellman-Ford for negative edges", "source_docs": [{"file": "handwritten_hard.png", "page": 1}, {"file": "slides_01_overview.pdf", "page": 8}]},
        {"id": 18, "type": "multi_doc", "question": "Compare BST and Heap for the operation of finding the minimum element.", "expected_answer": "Heap: O(1) find-min; BST: O(log n) (leftmost node)", "source_docs": [{"file": "lecture_02_trees.pdf", "page": 4}, {"file": "lecture_02_trees.pdf", "page": 3}]},
        {"id": 19, "type": "multi_doc", "question": "How do the sorting notes and lecture agree on Timsort?", "expected_answer": "Both: hybrid insertion+merge sort, stable, O(n log n) worst O(n) best", "source_docs": [{"file": "handwritten_clean.png", "page": 1}, {"file": "lecture_03_sorting.pdf", "page": 6}]},
        {"id": 20, "type": "multi_doc", "question": "What is the relationship between Max-Flow and Min-Cut according to the slides?", "expected_answer": "Max-Flow Min-Cut Theorem: max flow equals min cut capacity", "source_docs": [{"file": "slides_02_advanced.pdf", "page": 4}]},

        # Unanswerable (10)
        {"id": 21, "type": "unanswerable", "question": "Explain the Cook-Levin theorem and its significance.", "expected_answer": None, "source_docs": [], "syllabus_topic": "NP-Completeness proofs (not in corpus)"},
        {"id": 22, "type": "unanswerable", "question": "What is the Aho-Corasick algorithm?", "expected_answer": None, "source_docs": [], "syllabus_topic": "Advanced string algorithms"},
        {"id": 23, "type": "unanswerable", "question": "Derive the Strassen matrix multiplication recurrence.", "expected_answer": None, "source_docs": [], "syllabus_topic": "Strassen derivation (mentioned but not derived)"},
        {"id": 24, "type": "unanswerable", "question": "How does the Floyd-Warshall algorithm work step by step?", "expected_answer": None, "source_docs": [], "syllabus_topic": "Floyd-Warshall (only briefly mentioned in handwritten notes)"},
        {"id": 25, "type": "unanswerable", "question": "What is the Van Emde Boas tree?", "expected_answer": None, "source_docs": [], "syllabus_topic": "Advanced data structures"},
        {"id": 26, "type": "unanswerable", "question": "Explain the simplex method for linear programming.", "expected_answer": None, "source_docs": [], "syllabus_topic": "Linear programming"},
        {"id": 27, "type": "unanswerable", "question": "What is the Edmonds-Karp running time analysis?", "expected_answer": None, "source_docs": [], "syllabus_topic": "Network flow detailed analysis"},
        {"id": 28, "type": "unanswerable", "question": "Prove that 3-SAT reduces to Independent Set.", "expected_answer": None, "source_docs": [], "syllabus_topic": "NP reductions"},
        {"id": 29, "type": "unanswerable", "question": "How does the Splay Tree maintain amortized O(log n) operations?", "expected_answer": None, "source_docs": [], "syllabus_topic": "Splay trees"},
        {"id": 30, "type": "unanswerable", "question": "What is the randomized algorithm for matrix identity testing?", "expected_answer": None, "source_docs": [], "syllabus_topic": "Randomized algorithms"},
    ]

    eval_path.parent.mkdir(parents=True, exist_ok=True)
    with open(eval_path, "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=2)
    st.success(f"Generated {len(questions)} evaluation questions at `evaluation/questions.json`")
