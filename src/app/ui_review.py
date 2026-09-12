"""
Review tab: concept cards, document conflicts surface, syllabus coverage gaps.
"""
from __future__ import annotations

import sys
from pathlib import Path
import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _get_session():
    if "memory" not in st.session_state:
        from src.conversation.memory import ConversationMemory
        st.session_state.memory = ConversationMemory()
    if "session_mgr" not in st.session_state:
        from src.conversation.session import SessionManager
        st.session_state.session_mgr = SessionManager(st.session_state.memory)
    return st.session_state.memory, st.session_state.session_mgr


def render_review_tab():
    st.header("📋 Review & Study Tools")
    memory, session_mgr = _get_session()

    sub1, sub2, sub3, sub4 = st.tabs(
        ["💡 Concept Cards", "🔍 Concept Search", "⚡ Quiz Mode", "🗺️ Coverage"]
    )

    # ── Concept Cards ─────────────────────────────────────────────────────────
    with sub1:
        st.subheader("💡 Concept Cards")
        st.markdown("Save key concepts with source citations for quick revision.")

        # Create new card form
        with st.form("new_card_form"):
            st.markdown("**Create a new concept card:**")
            title = st.text_input("Concept name:")
            definition = st.text_area("Definition / explanation:", height=100)
            sources_input = st.text_input("Sources (comma-separated filenames):")
            save_card = st.form_submit_button("💾 Save Card")
            if save_card and title and definition:
                sources = [s.strip() for s in sources_input.split(",") if s.strip()]
                session_mgr.save_concept_card(title, definition, sources or ["manual"])
                st.success(f"Card '{title}' saved!")

        st.divider()

        # Display existing cards
        cards = session_mgr.state.concept_cards
        if not cards:
            st.info("No concept cards yet. Create one above or save an answer from the Ask tab.")
        else:
            st.markdown(f"**{len(cards)} concept cards:**")
            # Search filter
            card_search = st.text_input("Filter cards:", key="card_filter")
            filtered = [c for c in cards if not card_search or
                        card_search.lower() in c["title"].lower() or
                        card_search.lower() in c["definition"].lower()]

            cols = st.columns(2)
            for i, card in enumerate(filtered):
                with cols[i % 2]:
                    with st.container():
                        st.markdown(f"### {card['title']}")
                        st.markdown(card["definition"])
                        if card.get("sources"):
                            st.caption(f"Sources: {', '.join(card['sources'])}")
                        st.divider()

    # ── Concept Search ────────────────────────────────────────────────────────
    with sub2:
        st.subheader("🔍 Cross-document Concept Search")
        st.markdown("Search for a concept across ALL your documents and see where it appears.")

        concept_query = st.text_input("Search concept:", key="concept_search_query",
                                       placeholder="e.g. dynamic programming")
        if concept_query:
            try:
                from src.retrieval.vector_store import get_vector_store
                vs = get_vector_store()
                if vs.collection_size() == 0:
                    st.warning("No documents ingested yet.")
                else:
                    results = vs.search(concept_query, top_k=10)
                    st.markdown(f"**Found in {len(results)} passages across your corpus:**")

                    # Group by source
                    by_source: dict[str, list] = {}
                    for r in results:
                        meta = r.get("metadata", {})
                        src = meta.get("source_file", "?")
                        by_source.setdefault(src, []).append(r)

                    for src, passages in by_source.items():
                        with st.expander(f"📄 {src} ({len(passages)} passages)"):
                            for p in passages:
                                meta = p.get("metadata", {})
                                st.markdown(
                                    f'<span class="citation-badge">[{src}:{meta.get("page_number","?")}]</span>',
                                    unsafe_allow_html=True,
                                )
                                st.markdown(f'<div class="evidence-card">{p["text"][:300]}</div>',
                                            unsafe_allow_html=True)

            except Exception as exc:
                st.error(f"Search failed: {exc}")

    # ── Quiz Mode ─────────────────────────────────────────────────────────────
    with sub3:
        st.subheader("⚡ Quiz Mode")
        st.markdown("Generate questions from your materials for active recall practice.")

        if st.button("🎲 Generate Quiz Questions", type="primary"):
            with st.spinner("Generating questions from your corpus..."):
                try:
                    from src.retrieval.vector_store import get_vector_store
                    from src.generation.generator import generate_answer, configure_gemini
                    from src.generation.prompts import build_context_block

                    vs = get_vector_store()
                    if vs.collection_size() == 0:
                        st.warning("No documents ingested yet.")
                    else:
                        # Sample random chunks and generate questions
                        import random
                        all_results = vs.search("algorithm time complexity data structure", top_k=15)
                        sample = random.sample(all_results, min(6, len(all_results)))

                        configure_gemini()
                        context_block = build_context_block(sample)

                        import google.generativeai as genai
                        from src.config import GEMINI_API_KEY, GEMINI_MODEL
                        import os
                        key = GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
                        if not key:
                            st.error("No API key. Set GEMINI_API_KEY in .env")
                        else:
                            genai.configure(api_key=key)
                            quiz_prompt = (
                                "Based on the following course material excerpts, generate 5 study questions. "
                                "Format each as: Q: [question]  A: [brief answer] SOURCE: [source:page]\n\n"
                                + context_block
                            )
                            model = genai.GenerativeModel(GEMINI_MODEL)
                            response = model.generate_content(quiz_prompt)
                            st.session_state["quiz_output"] = response.text

                except Exception as exc:
                    st.error(f"Quiz generation failed: {exc}")

        if "quiz_output" in st.session_state:
            st.divider()
            st.markdown("**Generated Quiz Questions:**")
            st.markdown(st.session_state["quiz_output"])

            if st.button("🗑️ Clear quiz"):
                del st.session_state["quiz_output"]

    # ── Coverage ──────────────────────────────────────────────────────────────
    with sub4:
        st.subheader("🗺️ Syllabus Coverage")
        st.markdown("Check which syllabus topics are covered in your materials.")

        SYLLABUS_TOPICS = [
            "Arrays and linked lists",
            "Stacks and queues",
            "Binary search trees",
            "AVL trees / balanced BSTs",
            "Heaps and priority queues",
            "Hash tables",
            "Graph representations",
            "BFS and DFS",
            "Shortest paths (Dijkstra, Bellman-Ford)",
            "Minimum spanning trees",
            "Dynamic programming",
            "Greedy algorithms",
            "Sorting algorithms",
            "Divide and conquer / recurrences",
            "Master theorem",
            "NP-completeness",
            "Amortized analysis",
            "String algorithms (KMP, Rabin-Karp)",
        ]

        if st.button("🔍 Check Coverage"):
            try:
                from src.retrieval.vector_store import get_vector_store
                vs = get_vector_store()

                if vs.collection_size() == 0:
                    st.warning("No documents ingested yet.")
                else:
                    st.markdown("**Topic Coverage:**")
                    covered, uncovered = [], []

                    for topic in SYLLABUS_TOPICS:
                        results = vs.search(topic, top_k=3)
                        max_score = max((r["score"] for r in results), default=0.0)
                        is_covered = max_score > 0.45

                        if is_covered:
                            covered.append((topic, max_score,
                                           results[0]["metadata"].get("source_file","?") if results else "?"))
                        else:
                            uncovered.append(topic)

                    col_c, col_u = st.columns(2)
                    with col_c:
                        st.success(f"✅ Covered ({len(covered)})")
                        for topic, score, src in covered:
                            st.markdown(f"- **{topic}** `{score:.2f}` — *{src}*")

                    with col_u:
                        st.warning(f"❌ Not found ({len(uncovered)})")
                        for topic in uncovered:
                            st.markdown(f"- {topic}")

                    coverage_pct = len(covered) / len(SYLLABUS_TOPICS) * 100
                    st.metric("Overall coverage", f"{coverage_pct:.0f}%")

            except Exception as exc:
                st.error(f"Coverage check failed: {exc}")
