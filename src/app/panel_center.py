"""
Center panel — question bubble, structured answer, comparison table, chat input.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── Citation rendering ────────────────────────────────────────────────────────

_CIT_RE = re.compile(r"\[([^\[\]]+?):(\d+|[A-Za-z][\w\-]*)\]")

def _chips(text: str, low_sources: set[str] | None = None) -> str:
    """Replace [source:page] with coloured chip HTML."""
    low_sources = low_sources or set()
    def _replace(m: re.Match) -> str:
        src, page = m.group(1), m.group(2)
        cls = "cc-chip low" if src.lower() in low_sources else "cc-chip"
        return f'<span class="{cls}" title="Open {src} page {page}">[{src}:{page}]</span>'
    return _CIT_RE.sub(_replace, text)


# ── Comparison table detector & renderer ─────────────────────────────────────

_COMPARE_ASPECTS = [
    ("Edge weight requirement",   "edge weight", "negative"),
    ("Algorithmic approach",      "greedy|approach|method", "dynamic|relax"),
    ("Time complexity",           r"O\(", r"O\("),
    ("Negative-weight cycles",    "negative.weight|negative cycle", "detect"),
    ("Typical use cases",         "use case|application|road|GPS|GPS", "currency|arbitrage"),
    ("Space complexity",          "space|memory", "space|memory"),
    ("Stability",                 "stable|unstable", "stable|unstable"),
    ("In-place",                  "in.place", "in.place"),
]

def _detect_comparison(answer: str) -> tuple[str, str] | None:
    """
    If the answer is comparing two named things return (name_a, name_b).
    Very lightweight heuristic — looks for 'X ... Y' near 'compare|differ|vs|versus'.
    """
    patterns = [
        r"(?:difference between|compare|comparing|vs\.?|versus)\s+([\w'\-]+(?:\s+[\w'\-]+){0,3})\s+and\s+([\w'\-]+(?:\s+[\w'\-]+){0,3})",
        r"([\w'\-]+(?:\s+[\w'\-]+){0,3})\s+(?:and|vs\.?)\s+([\w'\-]+(?:\s+[\w'\-]+){0,3})\s+(?:differ|compare|both)",
    ]
    for pat in patterns:
        m = re.search(pat, answer, re.IGNORECASE)
        if m:
            a, b = m.group(1).strip(), m.group(2).strip()
            if 3 < len(a) < 40 and 3 < len(b) < 40:
                return a, b
    return None


def _extract_comparison_table(answer: str, name_a: str, name_b: str) -> list[tuple]:
    """
    Try to pull per-aspect content from the answer for each named entity.
    Returns list of (aspect, a_text, a_chips, b_text, b_chips).
    Falls back to empty if text is too unstructured.
    """
    rows = []
    sentences = re.split(r"(?<=[.!?])\s+", answer)
    cited = _CIT_RE.findall(answer)
    a_cits = [f"[{s}:{p}]" for s, p in cited if name_a.lower()[:5] in s.lower() or True]
    b_cits = [f"[{s}:{p}]" for s, p in cited if name_b.lower()[:5] in s.lower() or True]

    for aspect, pat_a, pat_b in _COMPARE_ASPECTS:
        a_sents = [s for s in sentences if re.search(pat_a, s, re.I) and name_a[:5].lower() in s.lower()]
        b_sents = [s for s in sentences if re.search(pat_b, s, re.I) and name_b[:5].lower() in s.lower()]
        if a_sents or b_sents:
            rows.append((aspect,
                         a_sents[0][:120] if a_sents else "—",
                         b_sents[0][:120] if b_sents else "—"))

    return rows[:6]   # cap at 6 rows


# ── Main answer renderer ──────────────────────────────────────────────────────

def _render_answer(result, chunks: list[dict]) -> None:
    """Render the structured answer: lead paragraph, sections, comparison table."""
    answer = result.answer
    low_srcs: set[str] = set()
    for c in chunks:
        meta = c.get("metadata", c)
        if float(meta.get("ocr_confidence", 1.0)) < 0.7:
            low_srcs.add(str(meta.get("source_file", "")).lower())

    if result.is_refusal:
        st.markdown(f"""
        <div style="background:#fffbeb;border:1px solid #fde68a;border-radius:10px;
            padding:16px 20px;margin-bottom:16px">
            <div style="font-weight:700;color:#92400e;margin-bottom:6px">
                🚫 Not found in your materials
            </div>
            <div style="font-size:.9rem;color:#78350f;line-height:1.6">{result.refusal_reason}</div>
        </div>""", unsafe_allow_html=True)
        return

    # Strip citations from plain text for paragraph display; show chips after each para
    paras = [p.strip() for p in re.split(r"\n{2,}", answer) if p.strip()]

    # Detect if this is a comparison answer
    query = st.session_state.get("current_query", "")
    comparison = _detect_comparison(query + " " + answer[:300])

    for i, para in enumerate(paras):
        # Detect section headings (## / bold lines)
        if re.match(r"^#{1,3}\s+", para):
            heading = re.sub(r"^#{1,3}\s+", "", para)
            st.markdown(f'<div class="cc-section-h">{heading}</div>', unsafe_allow_html=True)
            continue
        if re.match(r"^\*\*[^*]+\*\*\s*$", para.strip()):
            heading = para.strip().strip("*")
            st.markdown(f'<div class="cc-section-h">{heading}</div>', unsafe_allow_html=True)
            continue

        # Render paragraph with citation chips
        rendered = _chips(para, low_srcs)
        st.markdown(f'<div class="cc-para">{rendered}</div>', unsafe_allow_html=True)

    # ── Comparison table ──────────────────────────────────────────────────────
    if comparison:
        name_a, name_b = comparison
        rows = _extract_comparison_table(answer, name_a, name_b)

        if rows:
            st.markdown('<div class="cc-section-h">Comparison</div>', unsafe_allow_html=True)
            # Build HTML table
            cited_pairs = _CIT_RE.findall(answer)
            all_chips = " ".join(
                f'<span class="cc-chip">[{s}:{p}]</span>'
                for s, p in cited_pairs[:2]
            )

            table_html = f"""
            <table class="cc-table">
              <thead>
                <tr>
                  <th>Aspect</th>
                  <th>{name_a}</th>
                  <th>{name_b}</th>
                </tr>
              </thead>
              <tbody>
            """
            for aspect, a_text, b_text in rows:
                a_rendered = _chips(a_text, low_srcs)
                b_rendered = _chips(b_text, low_srcs)
                table_html += f"""
                <tr>
                  <td>{aspect}</td>
                  <td>{a_rendered}</td>
                  <td>{b_rendered}</td>
                </tr>
                """
            table_html += "</tbody></table>"
            st.markdown(table_html, unsafe_allow_html=True)


# ── Ask handler ───────────────────────────────────────────────────────────────

def _handle_query(query: str) -> None:
    """Run retrieval + generation and store results in session state."""
    try:
        from src.retrieval.vector_store import get_vector_store
        vs = get_vector_store()
        if vs.collection_size() == 0:
            st.warning("No corpus indexed yet. Ingest documents first (left panel).")
            return

        from src.ingestion.indexer import load_index
        from src.retrieval.hybrid_search import hybrid_search
        from src.retrieval.reranker import get_reranker
        from src.generation.generator import generate_answer, configure_gemini
        from src.conversation.query_expander import expand_query

        memory = st.session_state.memory
        session_mgr = st.session_state.session_mgr

        history = memory.get_history()
        expanded = expand_query(query, history, session_mgr.state)

        configure_gemini()
        vector_store, bm25_index = load_index()
        candidates = hybrid_search(expanded, vector_store, bm25_index, top_k=12)
        reranker = get_reranker()
        chunks = reranker.rerank(expanded, candidates, top_k=6)

        result = generate_answer(expanded, chunks, conversation_history=history)

        # Persist
        memory.add_turn("user", query)
        memory.add_turn(
            "assistant", result.answer,
            citations=[{"source": c.source_file, "page": c.page_number} for c in result.citations]
        )
        session_mgr.update_from_answer(query, result.answer, chunks, result.citations)

        st.session_state.current_query   = query
        st.session_state.current_result  = result
        st.session_state.current_chunks  = chunks

    except Exception as exc:
        st.error(f"Error: {exc}")
        import traceback
        st.code(traceback.format_exc())


# ── Main render ───────────────────────────────────────────────────────────────

def render_center_panel() -> None:
    result = st.session_state.get("current_result")
    query  = st.session_state.get("current_query", "")
    chunks = st.session_state.get("current_chunks", [])
    page   = st.session_state.get("page", "ask")

    # ── Pages other than ask ───────────────────────────────────────────────────
    if page == "home":
        _render_home()
        return
    if page == "saved":
        _render_saved()
        return
    if page == "revision":
        _render_revision()
        return
    if page == "settings":
        _render_settings()
        return

    # ── Ask page ───────────────────────────────────────────────────────────────
    # Question bubble
    if query:
        st.markdown(f'<div class="cc-question-bubble">{query}</div>', unsafe_allow_html=True)

    # Answer area
    scroll_area = st.container()
    with scroll_area:
        if result is None:
            st.markdown("""
            <div style="text-align:center;padding:60px 20px;color:#9ba3b6">
                <div style="font-size:2.5rem;margin-bottom:12px">📘</div>
                <div style="font-size:1rem;font-weight:600;color:#4d5469;margin-bottom:6px">
                    Ask anything about your course materials
                </div>
                <div style="font-size:.85rem">
                    Every answer is cited to the exact source page.<br>
                    Unanswerable questions are refused, not bluffed.
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            _render_answer(result, chunks)

    # ── Action row ─────────────────────────────────────────────────────────────
    if result and not result.is_refusal:
        st.markdown('<hr class="cc-divider">', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1.2, 1.2, 1.2])
        with c1:
            if st.button("↗ Open source", use_container_width=True):
                # Show first source chunk's page
                if chunks:
                    meta = chunks[0].get("metadata", chunks[0])
                    img = meta.get("page_image_path", "")
                    if img and Path(img).exists():
                        st.session_state.preview_image = img
        with c2:
            if st.button("⊞ Save comparison", use_container_width=True):
                session_mgr = st.session_state.session_mgr
                session_mgr.add_to_comparison(
                    label=query[:40],
                    text=result.answer[:300],
                    source=", ".join(set(c.source_file for c in result.citations)),
                )
                st.toast("Added to comparison!", icon="⊞")
        with c3:
            if st.button("📌 Pin for revision", use_container_width=True):
                mem = st.session_state.memory
                tid = mem.add_turn(
                    "assistant", result.answer,
                    citations=[{"src": c.source_file, "page": c.page_number} for c in result.citations]
                )
                mem.pin_turn(tid)
                st.toast("Pinned!", icon="📌")

    # ── Page image preview ─────────────────────────────────────────────────────
    if "preview_image" in st.session_state:
        img_p = st.session_state.preview_image
        if img_p and Path(img_p).exists():
            with st.expander("📄 Source page", expanded=True):
                st.image(img_p)
                if st.button("✕ Close"):
                    del st.session_state.preview_image

    # ── Chat input ─────────────────────────────────────────────────────────────
    st.markdown('<hr class="cc-divider">', unsafe_allow_html=True)
    with st.form("chat_form", clear_on_submit=True):
        user_q = st.text_input(
            "",
            placeholder="Ask another question about your course materials…",
            label_visibility="collapsed",
            key="chat_input",
        )
        submitted = st.form_submit_button("→", use_container_width=False)
        if submitted and user_q.strip():
            with st.spinner("Searching & generating…"):
                _handle_query(user_q.strip())
            st.rerun()


# ── Secondary pages ───────────────────────────────────────────────────────────

def _render_home() -> None:
    st.markdown("""
    <div style="padding:40px 20px">
      <h2 style="color:#1e2330">Welcome back 👋</h2>
      <p style="color:#7c8499;font-size:.9rem">
        Your citation-first study companion is ready.<br>
        Ask a question, or pick up where you left off.
      </p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("💬 Go to Ask", type="primary"):
        st.session_state.page = "ask"
        st.rerun()


def _render_saved() -> None:
    st.subheader("🔖 Saved Answers")
    mem = st.session_state.memory
    pinned = mem.get_pinned()
    if not pinned:
        st.info("No pinned answers yet. Use 'Pin for revision' in any answer.")
        return
    for p in pinned:
        with st.expander(p["content"][:60] + "…"):
            import re as _re
            _CHIP = _re.compile(r"\[([^\[\]]+?):(\d+|[A-Za-z][\w\-]*)\]")
            rendered = _CHIP.sub(
                lambda m: f'<span class="cc-chip">[{m.group(1)}:{m.group(2)}]</span>',
                p["content"]
            )
            st.markdown(rendered, unsafe_allow_html=True)
            st.caption(p["timestamp"][:19])


def _render_revision() -> None:
    st.subheader("📋 Revision")
    mgr = st.session_state.session_mgr
    cards = mgr.state.concept_cards
    if not cards:
        st.info("No concept cards yet. Save answers as cards from the Ask tab.")
        return
    for card in cards:
        with st.container(border=True):
            st.markdown(f"**{card['title']}**")
            st.markdown(card["definition"])
            if card.get("sources"):
                st.caption(f"Sources: {', '.join(card['sources'])}")


def _render_settings() -> None:
    import os
    st.subheader("⚙️ Settings")

    st.markdown("**Gemini API Key**")
    key_input = st.text_input("API key", type="password",
                               value=os.environ.get("GEMINI_API_KEY", ""),
                               key="settings_api_key")
    if st.button("Save key"):
        os.environ["GEMINI_API_KEY"] = key_input
        st.session_state.api_key_set = True
        st.success("API key saved for this session.")

    st.divider()
    st.markdown("**Corpus Ingestion**")
    force = st.checkbox("Force re-ingest all files")
    if st.button("🚀 Ingest Corpus", type="primary"):
        with st.spinner("Ingesting corpus…"):
            from src.ingestion.indexer import ingest_corpus
            summary = ingest_corpus(force_reingest=force)
        st.success(
            f"Done! {summary['total_documents']} documents, "
            f"{summary['total_chunks']} chunks."
        )
        if summary["errors"]:
            for e in summary["errors"]:
                st.error(e)
