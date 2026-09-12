"""
Study Thread tab: persistent multi-turn conversation with follow-up, pinned evidence, compare mode.
"""
from __future__ import annotations

import sys
import re
from pathlib import Path
import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _citation_badge(src: str, page: str) -> str:
    return f'<span class="citation-badge">[{src}:{page}]</span>'


def _get_or_create_session():
    if "memory" not in st.session_state:
        from src.conversation.memory import ConversationMemory
        st.session_state.memory = ConversationMemory()
    if "session_mgr" not in st.session_state:
        from src.conversation.session import SessionManager
        st.session_state.session_mgr = SessionManager(st.session_state.memory)
    return st.session_state.memory, st.session_state.session_mgr


def render_thread_tab():
    st.header("🧵 Study Thread")
    st.markdown(
        "Persistent multi-turn conversation. Ask follow-up questions — "
        "the workspace remembers what you've been discussing."
    )

    memory, session_mgr = _get_or_create_session()

    # ── Session management ─────────────────────────────────────────────────────
    with st.expander("📁 Session Management", expanded=False):
        sessions = memory.list_sessions()

        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            if st.button("➕ New Session"):
                sid = memory.new_session()
                from src.conversation.session import SessionManager
                st.session_state.session_mgr = SessionManager(memory)
                st.success(f"New session started")
                st.rerun()
        with col_s2:
            new_name = st.text_input("Rename session:", key="rename_session_input")
            if st.button("Rename") and new_name:
                memory.rename_session(new_name)
                st.success(f"Renamed to '{new_name}'")
        with col_s3:
            if sessions:
                session_options = {
                    f"{s['name'] or 'Unnamed'} ({s['session_id'][:8]}...)": s['session_id']
                    for s in sessions
                }
                chosen = st.selectbox("Switch to session:", list(session_options.keys()),
                                      key="switch_session_select")
                if st.button("Switch"):
                    memory.switch_session(session_options[chosen])
                    from src.conversation.session import SessionManager
                    st.session_state.session_mgr = SessionManager(memory)
                    st.rerun()

        session_info = memory.get_session_info()
        if session_info.get("topics"):
            st.caption(f"Active topics: {', '.join(session_info['topics'][:5])}")
        if session_info.get("docs_discussed"):
            st.caption(f"Documents discussed: {', '.join(session_info['docs_discussed'])}")

    # ── Chat history ───────────────────────────────────────────────────────────
    full_history = memory.get_full_history()

    st.subheader(f"Conversation ({len(full_history)} turns)")

    if not full_history:
        st.info("No conversation yet. Ask a question in the **💬 Ask** tab or type below.")
    else:
        for turn in full_history:
            role = turn["role"]
            content = turn["content"]
            citations = turn.get("citations", [])
            is_pinned = turn.get("is_pinned", False)
            turn_id = turn["id"]

            if role == "user":
                with st.chat_message("user"):
                    st.markdown(content)

            else:  # assistant
                with st.chat_message("assistant"):
                    if is_pinned:
                        st.markdown("📌 *Pinned*", unsafe_allow_html=True)

                    # Format citations inline
                    formatted = content
                    pattern = re.compile(r"\[([^\[\]]+?):(\d+|[A-Za-z][\w\-]*)\]")
                    def badge(m):
                        return f'<span class="citation-badge">[{m.group(1)}:{m.group(2)}]</span>'
                    formatted = pattern.sub(badge, formatted)
                    st.markdown(formatted, unsafe_allow_html=True)

                    # Pin / unpin button
                    col_p1, col_p2 = st.columns([1, 6])
                    with col_p1:
                        if not is_pinned:
                            if st.button("📌", key=f"pin_{turn_id}", help="Pin this answer"):
                                memory.pin_turn(turn_id)
                                st.rerun()
                        else:
                            if st.button("📍 Unpin", key=f"unpin_{turn_id}"):
                                memory.unpin_turn(turn_id)
                                st.rerun()

    # ── Follow-up input ────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Ask a follow-up")

    followup = st.text_input(
        "Follow-up question:",
        placeholder="e.g. How does it compare to Bellman-Ford? / Was that in the handwritten notes?",
        key="thread_followup",
    )

    if st.button("🔍 Ask Follow-up", type="primary", key="thread_submit"):
        if not followup.strip():
            st.warning("Please enter a question.")
            return

        _handle_followup(followup, memory, session_mgr)
        st.rerun()

    # ── Pinned evidence panel ──────────────────────────────────────────────────
    st.divider()
    st.subheader("📌 Pinned Evidence")

    pinned = memory.get_pinned()
    if not pinned:
        st.caption("No pinned answers yet. Click 📌 on any answer to pin it.")
    else:
        for p in pinned:
            with st.container():
                st.markdown(
                    f'<div class="pinned-card">'
                    f'<small>{p["timestamp"][:19]}</small><br>'
                    f'{p["content"][:300]}{"…" if len(p["content"])>300 else ""}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # ── Comparison mode ────────────────────────────────────────────────────────
    if session_mgr.state.comparison_queue:
        st.divider()
        st.subheader("⚖️ Comparison Table")
        st.markdown(session_mgr.get_comparison_table(), unsafe_allow_html=False)
        if st.button("🗑️ Clear comparison queue"):
            session_mgr.clear_comparison()
            st.rerun()


def _handle_followup(query: str, memory, session_mgr) -> None:
    """Process a follow-up question with full context."""
    try:
        from src.conversation.query_expander import expand_query
        from src.ingestion.indexer import load_index
        from src.retrieval.hybrid_search import hybrid_search
        from src.retrieval.reranker import get_reranker
        from src.generation.generator import generate_answer, configure_gemini

        history = memory.get_history()
        expanded = expand_query(query, history, session_mgr.state)
        if expanded != query:
            st.info(f"🔄 Expanded: *{expanded}*")

        configure_gemini()
        vector_store, bm25_index = load_index()
        candidates = hybrid_search(expanded, vector_store, bm25_index, top_k=12)

        reranker = get_reranker()
        chunks = reranker.rerank(expanded, candidates, top_k=6)

        result = generate_answer(expanded, chunks, conversation_history=history)

        memory.add_turn("user", query)
        memory.add_turn(
            "assistant", result.answer,
            citations=[{"source": c.source_file, "page": c.page_number} for c in result.citations]
        )
        session_mgr.update_from_answer(query, result.answer, chunks, result.citations)

    except Exception as exc:
        st.error(f"Follow-up failed: {exc}")
        import traceback
        st.code(traceback.format_exc())
