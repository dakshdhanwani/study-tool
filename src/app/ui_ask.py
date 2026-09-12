"""
Ask tab: grounded Q&A with inline citations, evidence cards, and refusal UI.
"""
from __future__ import annotations

import sys
import re
from pathlib import Path
import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _format_answer_with_citations(answer_text: str) -> str:
    """Replace [file:page] citations with coloured HTML badges."""
    pattern = re.compile(r"\[([^\[\]]+?):(\d+|[A-Za-z][\w\-]*)\]")

    def replace(m):
        src = m.group(1)
        page = m.group(2)
        return (f'<span class="citation-badge" title="Source: {src}, Page {page}">'
                f'[{src}:{page}]</span>')

    return pattern.sub(replace, answer_text)


def _get_or_create_session() -> tuple:
    """Return (ConversationMemory, SessionManager) from st.session_state."""
    if "memory" not in st.session_state:
        from src.conversation.memory import ConversationMemory
        st.session_state.memory = ConversationMemory()
    if "session_mgr" not in st.session_state:
        from src.conversation.session import SessionManager
        st.session_state.session_mgr = SessionManager(st.session_state.memory)
    return st.session_state.memory, st.session_state.session_mgr


def render_ask_tab():
    st.header("💬 Ask a Question")
    st.markdown("Ask anything about your course materials. Every claim will be cited by source + page.")

    memory, session_mgr = _get_or_create_session()

    # ── Query input ────────────────────────────────────────────────────────────
    col1, col2 = st.columns([4, 1])
    with col1:
        query = st.text_input(
            "Your question:",
            placeholder="e.g. What is the time complexity of Merge Sort?",
            key="ask_query",
        )
    with col2:
        use_context = st.checkbox("Use conversation context", value=True,
                                  help="Expand pronouns using conversation history.")

    # Advanced settings
    with st.expander("⚙️ Retrieval settings", expanded=False):
        top_k = st.slider("Chunks to retrieve", 3, 20, 6, key="ask_top_k")
        rerank = st.checkbox("Use reranker (slower, more precise)", value=True, key="ask_rerank")

    submit = st.button("🔍 Search & Answer", type="primary", use_container_width=False)

    if not submit or not query.strip():
        if not submit:
            _show_quick_start()
        return

    # ── Check prerequisites ────────────────────────────────────────────────────
    try:
        from src.retrieval.vector_store import get_vector_store
        vs = get_vector_store()
        if vs.collection_size() == 0:
            st.warning("⚠️ No documents ingested yet. Go to the **Materials** tab first.")
            return
    except Exception as exc:
        st.error(f"Could not connect to vector store: {exc}")
        return

    # ── Query expansion ────────────────────────────────────────────────────────
    final_query = query
    if use_context:
        try:
            from src.conversation.query_expander import expand_query
            history = memory.get_history()
            final_query = expand_query(query, history, session_mgr.state)
            if final_query != query:
                st.info(f"🔄 Query expanded to: *{final_query}*")
        except Exception:
            pass

    # ── Retrieval ──────────────────────────────────────────────────────────────
    with st.spinner("Searching your materials..."):
        try:
            from src.ingestion.indexer import load_index
            from src.retrieval.hybrid_search import hybrid_search
            from src.retrieval.reranker import get_reranker
            from src.config import RERANK_TOP_K

            vector_store, bm25_index = load_index()
            candidates = hybrid_search(final_query, vector_store, bm25_index, top_k=top_k * 2)

            if rerank and candidates:
                reranker = get_reranker()
                chunks = reranker.rerank(final_query, candidates, top_k=top_k)
            else:
                chunks = candidates[:top_k]

        except Exception as exc:
            st.error(f"Retrieval failed: {exc}")
            import traceback
            st.code(traceback.format_exc())
            return

    # ── Generation ─────────────────────────────────────────────────────────────
    with st.spinner("Generating grounded answer..."):
        try:
            from src.generation.generator import generate_answer, configure_gemini
            configure_gemini()
            history = memory.get_history() if use_context else []
            result = generate_answer(
                query=final_query,
                chunks=chunks,
                conversation_history=history,
            )
        except Exception as exc:
            st.error(f"Generation failed: {exc}")
            import traceback
            st.code(traceback.format_exc())
            return

    # ── Display result ─────────────────────────────────────────────────────────
    st.divider()

    if result.is_refusal:
        st.markdown(
            f'<div class="refusal-box">'
            f'<strong>🚫 Not found in your materials</strong><br><br>'
            f'{result.refusal_reason}'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.caption(f"I searched across {len(chunks)} retrieved passages but found no supporting evidence.")

    else:
        # Grounding score indicator
        score = result.grounding_score
        if score >= 0.8:
            score_icon, score_label = "🟢", "High"
        elif score >= 0.5:
            score_icon, score_label = "🟡", "Partial"
        else:
            score_icon, score_label = "🔴", "Low"

        col_ans, col_meta = st.columns([3, 1])
        with col_meta:
            st.metric("Citation score", f"{score_icon} {score:.0%}", help=f"Grounding: {score_label}")
            st.metric("Citations", len(result.citations))
            st.metric("Sources used", len(set(c.source_file for c in result.citations)))

        with col_ans:
            st.markdown("### Answer")
            formatted = _format_answer_with_citations(result.answer)
            st.markdown(formatted, unsafe_allow_html=True)

        # ── Evidence cards ────────────────────────────────────────────────────
        if chunks:
            with st.expander(f"📎 Evidence ({len(chunks)} passages retrieved)", expanded=True):
                for i, chunk in enumerate(chunks):
                    meta = chunk.get("metadata", chunk)
                    src = meta.get("source_file", chunk.get("source_file", "?"))
                    page = meta.get("page_number", chunk.get("page_number", "?"))
                    fmt = meta.get("format", chunk.get("format", "?"))
                    conf = float(meta.get("ocr_confidence", chunk.get("ocr_confidence", 1.0)))
                    text = chunk.get("text", "")
                    img_path = meta.get("page_image_path", chunk.get("page_image_path", ""))
                    rrf = chunk.get("rrf_score", 0.0)

                    with st.container():
                        c1, c2 = st.columns([5, 1])
                        with c1:
                            st.markdown(
                                f'<span class="citation-badge">[{src}:{page}]</span> '
                                f'<small>{fmt}</small>',
                                unsafe_allow_html=True,
                            )
                            if conf < 0.7:
                                st.markdown(
                                    f'<div class="ocr-warning">⚠️ Low OCR confidence: {conf:.0%}</div>',
                                    unsafe_allow_html=True,
                                )
                            st.markdown(f'<div class="evidence-card">{text[:400]}{"…" if len(text)>400 else ""}</div>',
                                        unsafe_allow_html=True)

                        with c2:
                            st.caption(f"Score: {rrf:.3f}")
                            if img_path and Path(img_path).exists():
                                if st.button(f"🖼️ View", key=f"view_img_{i}"):
                                    st.image(img_path, caption=f"{src} p{page}")

                    st.divider()

        # ── Pin and save actions ──────────────────────────────────────────────
        col_pin, col_card, col_compare = st.columns(3)

        with col_pin:
            if st.button("📌 Pin this answer", key="pin_answer"):
                turn_id = memory.add_turn(
                    "assistant", result.answer,
                    citations=[{"source": c.source_file, "page": c.page_number} for c in result.citations]
                )
                memory.pin_turn(turn_id)
                st.success("Pinned!")

        with col_card:
            if st.button("💾 Save as Concept Card", key="save_card"):
                st.session_state["pending_card"] = {
                    "answer": result.answer[:300],
                    "sources": list(set(c.source_file for c in result.citations)),
                }
                st.info("Enter a title below ↓")

        with col_compare:
            if st.button("➕ Add to Comparison", key="add_compare"):
                session_mgr.add_to_comparison(
                    label=query[:50],
                    text=result.answer[:300],
                    source=", ".join(set(c.source_file for c in result.citations)),
                )
                st.success("Added to comparison queue!")

        # Concept card form
        if "pending_card" in st.session_state:
            with st.form("card_form"):
                card_title = st.text_input("Card title:")
                submitted = st.form_submit_button("Save card")
                if submitted and card_title:
                    pc = st.session_state.pop("pending_card")
                    session_mgr.save_concept_card(card_title, pc["answer"], pc["sources"])
                    st.success(f"Concept card '{card_title}' saved!")

    # ── Save turn to memory ────────────────────────────────────────────────────
    memory.add_turn("user", query)
    if not result.is_refusal:
        memory.add_turn(
            "assistant", result.answer,
            citations=[{"source": c.source_file, "page": c.page_number} for c in result.citations]
        )
        session_mgr.update_from_answer(query, result.answer, chunks, result.citations)
    else:
        memory.add_turn("assistant", result.answer)


def _show_quick_start():
    st.markdown("""
    **Quick start:**
    1. Go to **📁 Materials** tab → Run Ingestion
    2. Come back here and ask a question
    3. Every claim will be cited with [source:page]
    4. Use **🧵 Study Thread** for multi-turn conversations

    **Example questions to try:**
    - *What is the time complexity of Dijkstra's algorithm?*
    - *Compare Merge Sort and Quicksort.*
    - *How does dynamic programming differ from greedy algorithms?*
    - *What does the handwritten note say about graph algorithms?*
    """)
