"""
Page router — dispatches to the correct page based on st.session_state.page.

BACKEND FUNCTIONS (unchanged):  _CIT, _chips, _detect_compare, _comparison_rows,
                                 _run_query, _delete_document, _ingest_files_cloud,
                                 _ingest_files, _friendly_name

UI FUNCTIONS (redesigned):       render_ask_page, _ask, _materials, _saved,
                                 _revision, _evaluation, _thread
                                 + all _render_* helpers
"""
from __future__ import annotations

import sys
import re
from pathlib import Path
import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ─────────────────────────────────────────────────────────────────────────────
# CITATION HELPERS — UNCHANGED
# ─────────────────────────────────────────────────────────────────────────────

_CIT = re.compile(r"\[([^\[\]]+?):(\d+|[A-Za-z][\w\-]*)\]")


def _chips(text: str, low: set[str] | None = None) -> str:
    low = low or set()
    def _r(m):
        s, p = m.group(1), m.group(2)
        cls = "cc-chip low" if s.lower() in low else "cc-chip"
        return f'<span class="{cls}">[{s}:{p}]</span>'
    return _CIT.sub(_r, text)


def _detect_compare(text: str) -> tuple[str, str] | None:
    m = re.search(
        r"(?:difference between|compare|comparing|vs\.?|versus)\s+([\w''\-]+(?:\s+[\w''\-]+){0,3})"
        r"\s+and\s+([\w''\-]+(?:\s+[\w''\-]+){0,3})",
        text, re.I
    )
    if m:
        a, b = m.group(1).strip(), m.group(2).strip()
        if 2 < len(a) < 50 and 2 < len(b) < 50:
            return a, b
    return None


def _comparison_rows(answer: str, a: str, b: str) -> list[tuple[str, str, str]]:
    """Extract (aspect, a_text, b_text) rows from answer text."""
    ASPECTS = [
        ("Edge weight constraint",  r"negative|weight",           r"negative|weight"),
        ("Approach",                r"greedy|approach|selects",   r"dynamic|relax|all edges"),
        ("Time complexity",         r"O\(",                       r"O\("),
        ("Negative cycles",         r"negative.cycle|cannot",     r"detect|negative.cycle"),
        ("Use cases",               r"use case|road|GPS|GPS",     r"arbitrage|currency|use case"),
        ("Space",                   r"space|memory",              r"space|memory"),
        ("Stability",               r"stable",                    r"stable"),
    ]
    sents = re.split(r"(?<=[.!?])\s+", answer)
    rows = []
    for aspect, pa, pb in ASPECTS:
        sa = [s for s in sents if re.search(pa, s, re.I) and a[:4].lower() in s.lower()]
        sb = [s for s in sents if re.search(pb, s, re.I) and b[:4].lower() in s.lower()]
        if sa or sb:
            rows.append((aspect,
                         sa[0][:130] if sa else "—",
                         sb[0][:130] if sb else "—"))
    return rows[:6]


# ─────────────────────────────────────────────────────────────────────────────
# RAG PIPELINE RUNNER — COMPLETELY UNCHANGED
# ─────────────────────────────────────────────────────────────────────────────

def _run_query(q: str) -> None:
    """Run full RAG pipeline and store in session state."""
    try:
        user_id = st.session_state.get("user_id", "")

        # ── Check if user has any indexed documents ───────────────────────────
        from src.storage.vector_store_supa import SupabaseVectorStore
        vs = SupabaseVectorStore(user_id)
        if vs.collection_size() == 0:
            st.warning("No documents indexed yet. Go to **📄 Materials** and upload files first.")
            return

        # ── Lazy BM25 build from Supabase chunk texts ─────────────────────────
        if st.session_state.get("bm25") is None:
            from src.ingestion.indexer import rebuild_bm25_for_user
            with st.spinner("Building keyword index…"):
                st.session_state.bm25 = rebuild_bm25_for_user(user_id)
        bm25 = st.session_state.bm25

        from src.retrieval.hybrid_search import hybrid_search
        from src.retrieval.reranker import get_reranker
        from src.generation.generator import generate_answer, configure_gemini
        from src.conversation.query_expander import expand_query

        mem = st.session_state.memory
        mgr = st.session_state.session_mgr

        history  = mem.get_history()
        expanded = expand_query(q, history, mgr.state)

        configure_gemini()
        candidates = hybrid_search(expanded, vs, bm25, top_k=14)
        chunks     = get_reranker().rerank(expanded, candidates, top_k=6)
        result     = generate_answer(expanded, chunks, conversation_history=history)

        mem.add_turn("user", q)
        mem.add_turn("assistant", result.answer,
                     citations=[{"source": c.source_file, "page": c.page_number}
                                 for c in result.citations])
        mgr.update_from_answer(q, result.answer, chunks, result.citations)

        st.session_state.query   = q
        st.session_state.result  = result
        st.session_state.chunks  = chunks
        st.session_state.history = mem.get_history()

    except Exception as exc:
        import traceback
        st.error(f"Pipeline error: {exc}")
        with st.expander("Stack trace"):
            st.code(traceback.format_exc())


# ─────────────────────────────────────────────────────────────────────────────
# FRIENDLY NAME HELPER — UNCHANGED
# ─────────────────────────────────────────────────────────────────────────────

def _friendly_name(src: str) -> str:
    mapping = {
        "lecture_01": "Lecture 01 · Data Structures",
        "lecture_02": "Lecture 02 · Trees & Heaps",
        "lecture_03": "Lecture 03 · Sorting",
        "slides_01":  "Slides 01 · Overview",
        "slides_02":  "Slides 02 · Advanced",
        "study_notes":"Study Notes",
        "handwritten_clean": "My Notes",
        "handwritten_hard":  "Maya's notes",
    }
    src_l = src.lower()
    for key, label in mapping.items():
        if key in src_l:
            return label
    return Path(src).stem.replace("_", " ").title()


# ─────────────────────────────────────────────────────────────────────────────
# PAGE ROUTER
# ─────────────────────────────────────────────────────────────────────────────

def render_ask_page() -> None:
    page = st.session_state.get("page", "ask")
    if page == "ask":
        _ask()
    elif page == "materials":
        _materials()
    elif page == "thread":
        _thread()
    elif page == "saved":
        _saved()
    elif page == "revision":
        _revision()


# ─────────────────────────────────────────────────────────────────────────────
# UI RENDER HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _render_topbar() -> None:
    """Full-width question search bar at the top of the Ask page."""
    with st.form("cc_chat_form", clear_on_submit=True):
        col_q, col_send = st.columns([7, 1])
        with col_q:
            user_q = st.text_input(
                "",
                placeholder="🔍  Ask anything about your course materials...",
                label_visibility="collapsed",
                key="cc_query_input",
            )
        with col_send:
            go = st.form_submit_button("↑", use_container_width=True, type="primary")
        if go and user_q.strip():
            with st.spinner("Searching & generating…"):
                _run_query(user_q.strip())
            st.rerun()


def _render_question(query: str) -> None:
    """Compact question display above the answer."""
    st.markdown(
        f'<div class="cc-question-bubble">{query}</div>',
        unsafe_allow_html=True,
    )


def _render_answer_section(result, chunks: list, query: str) -> None:
    """Render the full answer: paragraphs, sections, comparison table."""
    if result.is_refusal:
        _render_refusal_box(result, query)
        return

    # Collect low-confidence OCR sources for chip coloring
    low: set[str] = set()
    for c in chunks:
        meta = c.get("metadata", c)
        if float(meta.get("ocr_confidence", 1.0)) < 0.7:
            low.add(str(meta.get("source_file", "")).lower())

    paras = [p.strip() for p in re.split(r"\n{2,}", result.answer) if p.strip()]
    cmp   = _detect_compare(query + " " + result.answer[:200])

    for para in paras:
        # Section heading detection
        if re.match(r"^#{1,3}\s+", para):
            st.markdown(
                f'<div class="cc-section-h">{re.sub(r"^#{1,3}\s+", "", para)}</div>',
                unsafe_allow_html=True,
            )
            continue
        if re.match(r"^\*\*[^*]+\*\*\s*$", para.strip()):
            st.markdown(
                f'<div class="cc-section-h">{para.strip().strip("*")}</div>',
                unsafe_allow_html=True,
            )
            continue
        st.markdown(
            f'<div class="cc-para">{_chips(para, low)}</div>',
            unsafe_allow_html=True,
        )

    # Comparison table
    if cmp:
        a, b = cmp
        rows = _comparison_rows(result.answer, a, b)
        if rows:
            st.markdown('<div class="cc-section-h">Key Differences</div>', unsafe_allow_html=True)
            cells = "".join(
                f"<tr><td>{asp}</td>"
                f"<td>{_chips(at, low)}</td>"
                f"<td>{_chips(bt, low)}</td></tr>"
                for asp, at, bt in rows
            )
            st.markdown(
                f'<table class="cc-table"><thead><tr>'
                f'<th>Aspect</th><th>{a}</th><th>{b}</th>'
                f'</tr></thead><tbody>{cells}</tbody></table>',
                unsafe_allow_html=True,
            )


def _render_sources_strip(result) -> None:
    """Row of citation chips below the answer, above the action bar."""
    if not result.citations:
        return
    chips_html = "".join(
        f'<span class="cc-chip">{_friendly_name(c.source_file)} · p.{c.page_number}</span>'
        for c in result.citations[:6]
    )
    n = len(result.citations)
    label = f"Sources ({n})" if n > 0 else ""
    st.markdown(
        f'<div class="cc-sources-row">'
        f'<span class="cc-sources-label">{label}</span>'
        f'{chips_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_grounding_status(result) -> None:
    """Polished grounding status bar (green / amber)."""
    score = result.grounding_score
    n_cit = len(result.citations)
    if score >= 0.7:
        st.markdown(
            f'<div class="cc-grounding-ok">'
            f'<span style="font-size:1rem">✓</span>'
            f'<div class="cc-grounding-text">'
            f'<strong>Answer is well supported by your materials.</strong>'
            f'All key claims are backed by {n_cit} citation(s).'
            f'</div></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="cc-grounding-warn">'
            f'<span style="font-size:1rem">⚠</span>'
            f'<div class="cc-grounding-text">'
            f'<strong>Limited support in your materials.</strong>'
            f'Some claims have weak or incomplete evidence ({n_cit} citation(s)).'
            f'</div></div>',
            unsafe_allow_html=True,
        )


def _render_refusal_box(result, query: str) -> None:
    """Prominent refusal state — no answer rendered."""
    st.markdown(
        f'<div class="cc-refusal">'
        f'<div class="cc-refusal-title">⚠ Not covered by your materials</div>'
        f'<div class="cc-refusal-body">'
        f"I couldn't find enough evidence in your course materials to answer this reliably.<br>"
        f"I won't guess or use outside information."
        f'</div>'
        f'<div class="cc-refusal-q">"{query}"</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    if result.refusal_reason:
        st.caption(f"Details: {result.refusal_reason}")


def _render_action_bar(result, chunks: list, query: str) -> None:
    """Save / Compare / Pin action buttons below the answer."""
    st.markdown("<hr style='border:none;border-top:1px solid #f1f5f9;margin:14px 0 10px'>",
                unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("♡  Save to revision", use_container_width=True, key="cc_save_rev"):
            st.session_state.session_mgr.add_to_comparison(
                label=query[:40],
                text=result.answer[:300],
                source=", ".join({c.source_file for c in result.citations}),
            )
            st.toast("Saved to revision queue!", icon="♡")
    with c2:
        if st.button("⇄  Compare", use_container_width=True, key="cc_compare"):
            st.session_state.session_mgr.add_to_comparison(
                label=query[:40],
                text=result.answer[:300],
                source=", ".join({c.source_file for c in result.citations}),
            )
            st.toast("Added to comparison queue!", icon="⇄")
    with c3:
        if st.button("📌  Pin for revision", use_container_width=True, key="cc_pin"):
            mem = st.session_state.memory
            tid = mem.add_turn(
                "assistant", result.answer,
                citations=[{"src": c.source_file, "page": c.page_number}
                            for c in result.citations],
            )
            mem.pin_turn(tid)
            st.toast("Pinned!", icon="📌")


# ─────────────────────────────────────────────────────────────────────────────
# EVIDENCE PANEL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_icon(fmt: str) -> str:
    return {"pdf-lecture": "📄", "pdf-slide": "📊", "markdown": "📝",
            "handwritten": "✍️", "image-ocr": "✍️"}.get(fmt, "📄")


def _render_primary_evidence_card(chunk: dict, idx: int) -> None:
    """The dominant top evidence card with full page image."""
    meta  = chunk.get("metadata", chunk)
    src   = str(meta.get("source_file", "unknown"))
    page  = meta.get("page_number", "?")
    conf  = float(meta.get("ocr_confidence", 1.0))
    text  = (chunk.get("text") or "").strip()
    img_p = str(meta.get("page_image_path", chunk.get("page_image_path", "")))
    fmt   = str(meta.get("format", ""))

    is_hw  = fmt in ("handwritten", "image-ocr") or "handwritten" in src.lower()
    is_low = conf < 0.75
    excerpt = text[:200] + ("…" if len(text) > 200 else "")
    icon    = _fmt_icon(fmt)

    st.markdown(
        f'<div class="cc-ecard-primary">'
        f'<div class="cc-ecard-hdr">'
        f'<span style="font-size:.95rem">{icon}</span>'
        f'<div style="flex:1;overflow:hidden">'
        f'<div class="cc-ecard-doc-title">{_friendly_name(src)}</div>'
        f'<div class="cc-ecard-doc-sub">{src}</div>'
        f'</div>'
        f'<div class="cc-ecard-page-badge">p. {page}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Page image (actual, from metadata)
    if img_p and Path(img_p).exists():
        st.image(img_p, use_container_width=True)

    # OCR confidence warning
    if is_hw and is_low:
        st.markdown(
            f'<div class="cc-ocr-badge">⚠ Low confidence OCR</div>'
            f'<div class="cc-ocr-warning">'
            f'This page is handwritten and OCR may be imperfect. '
            f'Here is the original image so you can verify it.</div>',
            unsafe_allow_html=True,
        )
    elif is_hw:
        st.markdown(
            f'<div class="cc-ocr-badge" style="background:#dcfce7;color:#166534">'
            f'✍️ OCR {conf:.0%}</div>',
            unsafe_allow_html=True,
        )

    # Excerpt
    st.markdown(
        f'<blockquote class="cc-ecard-quote">"{excerpt}"</blockquote>',
        unsafe_allow_html=True,
    )

    # Open source button
    btn_col, _ = st.columns([1, 2])
    with btn_col:
        if st.button("↗ Open source", key=f"cc_ev_open_{idx}_{src}_{page}"):
            if img_p and Path(img_p).exists():
                st.session_state.preview_img = img_p
            else:
                st.toast(f"{src} · page {page}")

    st.markdown('</div>', unsafe_allow_html=True)


def _render_secondary_cards(chunks: list, idx_offset: int = 1) -> None:
    """Two-column grid of smaller 'Also cited' evidence cards."""
    if not chunks:
        return

    st.markdown('<div class="cc-also-label">Also cited</div>', unsafe_allow_html=True)

    cols = st.columns(min(len(chunks), 2))
    for i, chunk in enumerate(chunks[:4]):
        meta  = chunk.get("metadata", chunk)
        src   = str(meta.get("source_file", "unknown"))
        page  = meta.get("page_number", "?")
        conf  = float(meta.get("ocr_confidence", 1.0))
        text  = (chunk.get("text") or "").strip()
        img_p = str(meta.get("page_image_path", chunk.get("page_image_path", "")))
        fmt   = str(meta.get("format", ""))
        is_hw = fmt in ("handwritten", "image-ocr") or "handwritten" in src.lower()
        excerpt = text[:100] + ("…" if len(text) > 100 else "")

        with cols[i % 2]:
            st.markdown('<div class="cc-ecard-sec">', unsafe_allow_html=True)

            if img_p and Path(img_p).exists():
                st.image(img_p, use_container_width=True)

            st.markdown(
                f'<div class="cc-ecard-sec-info">'
                f'<div class="cc-ecard-sec-title">{_friendly_name(src)}</div>'
                f'<div class="cc-ecard-sec-page">p. {page}</div>'
                f'</div>'
                f'<blockquote class="cc-ecard-sec-quote">"{excerpt}"</blockquote>',
                unsafe_allow_html=True,
            )

            if is_hw and conf < 0.75:
                st.markdown(
                    f'<div class="cc-ocr-badge" style="margin:0 12px 8px">⚠ OCR {conf:.0%}</div>',
                    unsafe_allow_html=True,
                )

            if st.button("↗", key=f"cc_ev_sec_{idx_offset + i}_{src}_{page}",
                         help=f"Open {src} p.{page}"):
                if img_p and Path(img_p).exists():
                    st.session_state.preview_img = img_p
                else:
                    st.toast(f"{src} · page {page}")

            st.markdown('</div>', unsafe_allow_html=True)


def _render_evidence_panel(result, chunks: list, query: str) -> None:
    """Right-side evidence panel with tabs: Evidence | Related | Notes."""
    st.markdown(
        '<div class="cc-ev-title">Evidence</div>'
        '<div class="cc-ev-sub">Pages from your course materials that support this answer.</div>',
        unsafe_allow_html=True,
    )

    tab_ev, tab_rel, tab_notes = st.tabs(["Evidence", "Related", "Notes"])

    with tab_ev:
        if result is None:
            st.markdown(
                '<div style="color:#9ba3b6;font-size:.83rem;padding:20px 0">'
                'Evidence cards appear here after you ask a question.'
                '</div>',
                unsafe_allow_html=True,
            )
            return

        if result.is_refusal:
            st.markdown(
                f'<div class="cc-refusal">'
                f'<div class="cc-refusal-title">⚠ Not in your materials</div>'
                f'<div class="cc-refusal-body">{result.refusal_reason}</div>'
                f'<div class="cc-refusal-q">"{query}"</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            return

        # Primary evidence card (strongest source)
        if chunks:
            _render_primary_evidence_card(chunks[0], 0)

        # Secondary cards
        if len(chunks) > 1:
            _render_secondary_cards(chunks[1:], idx_offset=1)

        # Grounding score footer
        if result.citations:
            s = result.grounding_score
            icon = "🟢" if s >= 0.8 else ("🟡" if s >= 0.5 else "🔴")
            st.markdown(
                f"<div style='font-size:.74rem;color:#7c8499;padding:8px 0'>"
                f"{icon} Grounding score: <b>{s:.0%}</b> "
                f"· {len(result.citations)} citation(s)</div>",
                unsafe_allow_html=True,
            )

    with tab_rel:
        st.caption("Documents discussed in the current session:")
        mgr = st.session_state.get("session_mgr")
        if mgr and hasattr(mgr.state, "docs_discussed") and mgr.state.docs_discussed:
            for doc in mgr.state.docs_discussed[:8]:
                st.caption(f"📄 {doc}")
        else:
            st.caption("Ask more questions to discover related topics.")

        cmp_q = st.session_state.get("session_mgr")
        if cmp_q and hasattr(cmp_q, "state") and cmp_q.state.comparison_queue:
            st.divider()
            st.markdown("**⚖️ Comparison queue**")
            st.markdown(cmp_q.get_comparison_table(), unsafe_allow_html=False)
            if st.button("Clear comparison", key="cc_clear_cmp"):
                cmp_q.clear_comparison()
                st.rerun()

    with tab_notes:
        mgr = st.session_state.get("session_mgr")
        if mgr and hasattr(mgr.state, "concept_cards") and mgr.state.concept_cards:
            for card in mgr.state.concept_cards[:6]:
                with st.container(border=True):
                    st.markdown(f"**{card['title']}**")
                    st.caption(card.get("definition", "")[:120])
        else:
            st.caption("No concept cards yet.")
            st.caption("Go to **📋 Revision** to create concept cards.")


# ─────────────────────────────────────────────────────────────────────────────
# ASK PAGE
# ─────────────────────────────────────────────────────────────────────────────

def _ask() -> None:
    result = st.session_state.result
    chunks = st.session_state.chunks
    query  = st.session_state.query

    # ── Top search bar ────────────────────────────────────────────────────────
    _render_topbar()

    # ── Two-column layout: center workspace | evidence panel ──────────────────
    center_col, ev_col = st.columns([1.75, 1.0], gap="large")

    # ──────────────────── CENTER / STUDY WORKSPACE ────────────────────────────
    with center_col:
        if query:
            _render_question(query)

        if result is None:
            st.markdown(
                '<div class="cc-empty">'
                '<div class="cc-empty-icon">📘</div>'
                '<div class="cc-empty-title">Ask anything about your course materials</div>'
                '<div class="cc-empty-sub">'
                'Every answer is cited to the exact source page.<br>'
                'Unsupported questions are refused, not bluffed.'
                '</div></div>',
                unsafe_allow_html=True,
            )
        else:
            _render_answer_section(result, chunks, query)

            if not result.is_refusal:
                _render_sources_strip(result)
                _render_grounding_status(result)
                _render_action_bar(result, chunks, query)

        # Page image preview (triggered by "Open source" buttons)
        if "preview_img" in st.session_state:
            p = st.session_state.preview_img
            if p and Path(p).exists():
                with st.expander("📄 Source page", expanded=True):
                    st.image(p)
                    if st.button("✕ Close preview", key="cc_close_preview"):
                        del st.session_state.preview_img

    # ──────────────────── EVIDENCE PANEL ─────────────────────────────────────
    with ev_col:
        _render_evidence_panel(result, chunks, query)


# ─────────────────────────────────────────────────────────────────────────────
# MATERIALS PAGE  (upload + ingest)
# ─────────────────────────────────────────────────────────────────────────────

def _materials() -> None:
    # Header
    hdr_col, btn_col = st.columns([3, 1])
    with hdr_col:
        st.title("📄 My Materials")
        st.caption("Your course knowledge base — upload, index, and manage documents.")
    with btn_col:
        st.markdown("<div style='padding-top:24px'>", unsafe_allow_html=True)
        if st.button("＋ Upload material", type="primary", use_container_width=True,
                     key="mat_upload_shortcut"):
            st.session_state.mat_show_upload = True
        st.markdown("</div>", unsafe_allow_html=True)

    user_id = st.session_state.get("user_id", "")

    # ── Processing status bar ─────────────────────────────────────────────────
    try:
        from src.storage.registry_supa import SupabaseDocumentRegistry
        docs = SupabaseDocumentRegistry(user_id).list_documents()
        total_pages  = sum(int(d.get("page_count", 0) or 0) for d in docs)
        total_chunks = sum(int(d.get("chunk_count", 0) or 0) for d in docs)
        if total_pages > 0:
            pct = min(100, 100)
            st.markdown(
                f"<div style='font-size:.82rem;color:#6b7280;margin-bottom:4px'>"
                f"{total_pages} / {total_pages} pages processed · {total_chunks:,} chunks indexed"
                f"</div>"
                f"<div style='background:#e8edf5;border-radius:4px;height:5px;overflow:hidden;margin-bottom:16px'>"
                f"<div style='background:#3b5bdb;height:100%;width:{pct}%;border-radius:4px'></div>"
                f"</div>",
                unsafe_allow_html=True,
            )
    except Exception:
        pass

    # ── Upload section ────────────────────────────────────────────────────────
    show_upload = st.session_state.get("mat_show_upload", False)
    with st.expander("📥 Upload new files", expanded=show_upload):
        st.caption(
            "Supported: `.pdf` (lectures/slides) · `.md` `.txt` (notes) · "
            "`.png` `.jpg` `.jpeg` (handwritten scans)"
        )
        col_type, col_up = st.columns([1, 2])
        with col_type:
            doc_type = st.radio(
                "Document type:",
                ["📄 Lecture PDF", "📊 Slide PDF", "📝 Notes (md/txt)", "✍️ Handwritten photo"],
                label_visibility="visible",
            )
        with col_up:
            ext_map  = {
                "📄 Lecture PDF":         ["pdf"],
                "📊 Slide PDF":           ["pdf"],
                "📝 Notes (md/txt)":      ["md", "txt"],
                "✍️ Handwritten photo":   ["png", "jpg", "jpeg"],
            }
            cat_map  = {
                "📄 Lecture PDF":         "lectures",
                "📊 Slide PDF":           "slides",
                "📝 Notes (md/txt)":      "notes",
                "✍️ Handwritten photo":   "handwritten",
            }
            allowed  = ext_map[doc_type]
            category = cat_map[doc_type]

            uploaded = st.file_uploader(
                "Drop files here or click to browse",
                type=allowed,
                accept_multiple_files=True,
                label_visibility="collapsed",
            )

        if uploaded:
            st.markdown(f"**{len(uploaded)} file(s) ready to upload:**")
            upload_results = []

            for f in uploaded:
                try:
                    from src.storage.file_store import upload_file
                    storage_path = upload_file(
                        user_id=user_id,
                        category=category,
                        filename=f.name,
                        data=f.getvalue(),
                    )
                    upload_results.append((f, storage_path, True))
                    st.markdown(
                        f'<div class="cc-mat-row">'
                        f'<span class="cc-mat-name">{f.name}</span>'
                        f'<span class="cc-mat-meta">{f.size/1024:.1f} KB · {category}</span>'
                        f'<span class="cc-badge-ok">Uploaded ✓</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                except Exception as exc:
                    upload_results.append((f, "", False))
                    st.markdown(
                        f'<div class="cc-mat-row">'
                        f'<span class="cc-mat-name">{f.name}</span>'
                        f'<span class="cc-mat-meta">Upload failed: {exc}</span>'
                        f'<span class="cc-badge-err">Error</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

            successful = [(f, sp) for f, sp, ok in upload_results if ok]

            st.markdown("")
            if successful and st.button(
                "🚀 Index uploaded files", type="primary",
                use_container_width=True, key="mat_index_btn",
            ):
                _ingest_files_cloud(user_id, successful, category)
                from src.app.sidebar import _chunk_count, _registered_docs
                _chunk_count.clear()
                _registered_docs.clear()
                st.session_state.bm25 = None
                st.session_state.mat_show_upload = False

    st.markdown("")

    # ── Indexed documents table ───────────────────────────────────────────────
    with st.container(border=True):
        st.subheader("Indexed documents")
        st.caption("Click 🗑️ to remove a document from the index and storage.")

        try:
            from src.storage.registry_supa import SupabaseDocumentRegistry
            docs = SupabaseDocumentRegistry(user_id).list_documents()
        except Exception:
            docs = []

        if not docs:
            st.info(
                "No documents indexed yet. Upload files above and click **Index uploaded files**."
            )
        else:
            # Table header
            h1, h2, h3, h4, h5, h6 = st.columns([3, 1.2, 1, 1, 1.2, 0.6])
            h1.markdown("**Document**")
            h2.markdown("**Type**")
            h3.markdown("**Pages**")
            h4.markdown("**Chunks**")
            h5.markdown("**Indexed**")
            h6.markdown("")
            st.divider()

            fmt_icon = {"pdf-lecture": "📄", "pdf-slide": "📊", "markdown": "📝",
                        "text": "📄", "handwritten": "✍️", "image-ocr": "✍️"}
            fmt_label = {"pdf-lecture": "PDF", "pdf-slide": "Slides", "markdown": "Markdown",
                         "text": "Text", "handwritten": "Handwritten", "image-ocr": "OCR Image"}

            for doc in docs:
                icon = fmt_icon.get(doc.get("format", ""), "📄")
                fmtl = fmt_label.get(doc.get("format", ""), "—")
                c1, c2, c3, c4, c5, c6 = st.columns([3, 1.2, 1, 1, 1.2, 0.6])
                c1.markdown(f"{icon} **{doc['source_file']}**")
                c2.markdown(f"<span style='font-size:.82rem;color:#6b7280'>{fmtl}</span>",
                            unsafe_allow_html=True)
                c3.markdown(f"<span style='font-size:.82rem'>{doc.get('page_count', '?')}</span>",
                            unsafe_allow_html=True)
                c4.markdown(f"<span style='font-size:.82rem'>{doc.get('chunk_count', '?')}</span>",
                            unsafe_allow_html=True)
                c5.markdown(
                    f"<span class='cc-badge-ok'>✓ Indexed</span>",
                    unsafe_allow_html=True,
                )
                if c6.button("🗑️", key=f"del_{doc['source_file']}",
                             help=f"Remove {doc['source_file']}"):
                    _delete_document(user_id, doc["source_file"], doc.get("storage_path", ""))
                    from src.app.sidebar import _chunk_count, _registered_docs
                    _chunk_count.clear()
                    _registered_docs.clear()
                    st.session_state.bm25 = None
                    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# STUDY THREAD PAGE — uses Supabase memory from session state
# ─────────────────────────────────────────────────────────────────────────────

def _thread() -> None:
    st.title("💭 Study Thread")
    st.caption("Your persistent multi-turn study conversation — pick up right where you left off.")

    mem = st.session_state.memory
    mgr = st.session_state.session_mgr

    # ── Session management bar ────────────────────────────────────────────────
    with st.expander("📁 Session management", expanded=False):
        s1, s2, s3 = st.columns(3)
        with s1:
            if st.button("➕ New session", key="thread_new"):
                mem.new_session()
                from src.conversation.session import SessionManager
                st.session_state.session_mgr = SessionManager(mem)
                st.session_state.result  = None
                st.session_state.chunks  = []
                st.session_state.query   = ""
                st.session_state.history = []
                st.rerun()
        with s2:
            new_name = st.text_input("Rename session:", key="thread_rename_input")
            if st.button("Rename", key="thread_rename_btn") and new_name:
                mem.rename_session(new_name)
                st.success(f"Renamed to '{new_name}'")
        with s3:
            try:
                sessions = mem.list_sessions()
                if sessions:
                    opts = {
                        f"{s.get('name') or 'Unnamed'} ({s['session_id'][:8]}…)": s["session_id"]
                        for s in sessions
                    }
                    chosen = st.selectbox("Switch to:", list(opts.keys()), key="thread_switch_sel")
                    if st.button("Switch", key="thread_switch_btn"):
                        mem.switch_session(opts[chosen])
                        from src.conversation.session import SessionManager
                        st.session_state.session_mgr = SessionManager(mem)
                        st.session_state.result  = None
                        st.session_state.chunks  = []
                        st.session_state.query   = ""
                        st.rerun()
            except Exception:
                pass

    # ── Conversation history ──────────────────────────────────────────────────
    try:
        history = mem.get_full_history()
    except Exception:
        history = [{"role": r["role"], "content": r["content"], "id": None,
                    "is_pinned": False, "timestamp": "", "citations": []}
                   for r in mem.get_history()]

    if not history:
        st.markdown(
            '<div class="cc-empty" style="padding:40px 0">'
            '<div class="cc-empty-icon">💭</div>'
            '<div class="cc-empty-title">No conversation yet</div>'
            '<div class="cc-empty-sub">Ask a question in the <b>💬 Ask</b> tab or use the input below.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        for turn in history:
            role     = turn["role"]
            content  = turn["content"]
            turn_id  = turn.get("id")
            is_pinned = turn.get("is_pinned", False)
            ts       = turn.get("timestamp", "")[:16].replace("T", " ")

            if role == "user":
                st.markdown(
                    f'<div class="cc-thread-q">{content}</div>',
                    unsafe_allow_html=True,
                )
            else:
                # Format citations in assistant answer
                formatted = _chips(content)
                pin_label = "📌 Pinned" if is_pinned else ""
                st.markdown(
                    f'<div class="cc-thread-meta">{pin_label} {ts}</div>'
                    f'<div class="cc-thread-a">{formatted}</div>',
                    unsafe_allow_html=True,
                )
                if turn_id:
                    pin_col, _ = st.columns([1, 5])
                    with pin_col:
                        if not is_pinned:
                            if st.button("📌 Pin", key=f"t_pin_{turn_id}"):
                                mem.pin_turn(turn_id)
                                st.rerun()
                        else:
                            if st.button("📍 Unpin", key=f"t_unpin_{turn_id}"):
                                mem.unpin_turn(turn_id)
                                st.rerun()

    # ── Pinned evidence ───────────────────────────────────────────────────────
    pinned = []
    try:
        pinned = mem.get_pinned()
    except Exception:
        pass

    if pinned:
        st.divider()
        st.subheader("📌 Pinned answers")
        for p in pinned:
            with st.container(border=True):
                st.markdown(f"<div class='cc-saved-body'>{_chips(p['content'][:400])}</div>",
                            unsafe_allow_html=True)
                st.caption(str(p.get("timestamp", ""))[:16].replace("T", " "))

    # ── Follow-up input ───────────────────────────────────────────────────────
    st.divider()
    st.markdown("**Ask a follow-up question**")
    st.caption("The system remembers your current conversation context.")

    with st.form("cc_thread_form", clear_on_submit=True):
        col_q, col_send = st.columns([7, 1])
        with col_q:
            followup = st.text_input(
                "",
                placeholder="📎  Ask a follow-up question...",
                label_visibility="collapsed",
                key="cc_thread_input",
            )
        with col_send:
            submitted = st.form_submit_button("↑", use_container_width=True, type="primary")

        if submitted and followup.strip():
            with st.spinner("Searching & generating…"):
                # Use the same Supabase-backed _run_query (NOT local indexer)
                _run_query(followup.strip())
            # Switch to Ask page to show the new result
            st.session_state.page = "ask"
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# SAVED PAGE
# ─────────────────────────────────────────────────────────────────────────────

def _saved() -> None:
    st.title("🔖 Saved for revision")
    st.caption("Answers you've pinned for later review.")

    mem    = st.session_state.memory
    pinned = mem.get_pinned()

    if not pinned:
        st.markdown(
            '<div class="cc-empty">'
            '<div class="cc-empty-icon">🔖</div>'
            '<div class="cc-empty-title">No saved answers yet</div>'
            '<div class="cc-empty-sub">Use <b>📌 Pin for revision</b> after any answer.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    for p in pinned:
        content   = p["content"]
        ts        = str(p.get("timestamp", ""))[:16].replace("T", " ")
        citations = p.get("citations", [])
        title_txt = content[:60] + "…" if len(content) > 60 else content

        src_str = ""
        if citations:
            srcs = list({c.get("src") or c.get("source", "") for c in citations if c})
            src_str = ", ".join(f"{s}" for s in srcs[:3] if s)

        st.markdown(
            f'<div class="cc-saved-card">'
            f'<div class="cc-saved-title">{title_txt}</div>'
            f'<div class="cc-saved-body">{_chips(content[:400])}</div>'
            f'{"<div class=\"cc-sources-row\"><span class=\"cc-sources-label\">Sources</span>" + src_str + "</div>" if src_str else ""}'
            f'<div class="cc-saved-ts">{ts}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        btn1, btn2, _ = st.columns([1, 1, 4])
        with btn1:
            if st.button("Unpin", key=f"cc_unpin_{p['id']}"):
                mem.unpin_turn(p["id"])
                st.rerun()
        with btn2:
            if st.button("Open thread", key=f"cc_open_thread_{p['id']}"):
                st.session_state.page = "thread"
                st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# REVISION PAGE
# ─────────────────────────────────────────────────────────────────────────────

def _revision() -> None:
    hdr_col, btn_col = st.columns([3, 1])
    with hdr_col:
        st.title("📋 Revision")
        st.caption("Your personal concept cards — built from your course materials.")
    with btn_col:
        st.markdown("<div style='padding-top:24px'>", unsafe_allow_html=True)
        if st.button("＋ New concept", type="primary", use_container_width=True,
                     key="rev_new_btn"):
            st.session_state.rev_show_form = True
        st.markdown("</div>", unsafe_allow_html=True)

    mgr   = st.session_state.session_mgr
    cards = mgr.state.concept_cards

    # New card form
    if st.session_state.get("rev_show_form", False):
        with st.form("cc_new_card"):
            st.subheader("New concept card")
            title = st.text_input("Concept name")
            defn  = st.text_area("Definition / key points", height=80)
            srcs  = st.text_input("Sources (comma-separated)")
            s1, s2 = st.columns(2)
            saved = s1.form_submit_button("Save card", type="primary")
            cancel = s2.form_submit_button("Cancel")
            if saved and title:
                mgr.save_concept_card(
                    title, defn,
                    [s.strip() for s in srcs.split(",") if s.strip()],
                )
                st.success("Saved!")
                st.session_state.rev_show_form = False
                st.rerun()
            if cancel:
                st.session_state.rev_show_form = False
                st.rerun()

    st.divider()

    if not cards:
        st.markdown(
            '<div class="cc-empty">'
            '<div class="cc-empty-icon">📋</div>'
            '<div class="cc-empty-title">No concept cards yet</div>'
            '<div class="cc-empty-sub">Create a card above, or save answers from the Ask page.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    cols = st.columns(2)
    for i, card in enumerate(cards):
        with cols[i % 2]:
            srcs_str = ", ".join(card.get("sources", []))
            st.markdown(
                f'<div class="cc-rev-card">'
                f'<div class="cc-rev-title">{card["title"]}</div>'
                f'<div class="cc-rev-body">{card.get("definition", "")}</div>'
                f'{"<div class=\"cc-rev-src\">Sources: " + srcs_str + "</div>" if srcs_str else ""}'
                f'</div>',
                unsafe_allow_html=True,
            )


# ─────────────────────────────────────────────────────────────────────────────
# EVALUATION PAGE
# ─────────────────────────────────────────────────────────────────────────────

def _evaluation() -> None:
    import json
    st.title("🧪 Evaluation")
    st.caption(
        "Run the **30-question benchmark** (10 single-doc · 10 multi-doc · 10 unanswerable). "
        "The app grades itself automatically."
    )
    eval_path = PROJECT_ROOT / "evaluation" / "questions.json"

    if not eval_path.exists():
        st.info("Evaluation questions not generated yet.")
        if st.button("Generate 30-question set", key="eval_gen"):
            from src.app.ui_evaluation import _generate_questions
            _generate_questions(eval_path)
            st.rerun()
        return

    with open(eval_path) as f:
        qs = json.load(f)

    c1, c2, c3 = st.columns(3)
    c1.metric("Single-doc",   sum(1 for q in qs if q["type"] == "single_doc"))
    c2.metric("Multi-doc",    sum(1 for q in qs if q["type"] == "multi_doc"))
    c3.metric("Unanswerable", sum(1 for q in qs if q["type"] == "unanswerable"))

    st.divider()

    subset = st.selectbox("Run subset", ["All 30", "Single-doc", "Multi-doc", "Unanswerable"],
                          key="eval_subset")
    map_   = {
        "All 30":       qs,
        "Single-doc":   [q for q in qs if q["type"] == "single_doc"],
        "Multi-doc":    [q for q in qs if q["type"] == "multi_doc"],
        "Unanswerable": [q for q in qs if q["type"] == "unanswerable"],
    }

    if st.button("▶ Run Evaluation", type="primary", key="eval_run"):
        from src.app.ui_evaluation import _run_eval, _show_results
        results_dir = PROJECT_ROOT / "evaluation" / "results"
        with st.spinner(f"Running {len(map_[subset])} questions…"):
            results = _run_eval(map_[subset])
        if results:
            _show_results(results, results_dir)


# ─────────────────────────────────────────────────────────────────────────────
# BACKEND HELPERS — COMPLETELY UNCHANGED
# ─────────────────────────────────────────────────────────────────────────────

def _delete_document(user_id: str, source_file: str, storage_path: str = "") -> None:
    """Remove a document from Supabase pgvector, registry, and Storage."""
    # 1. Remove vectors
    try:
        from src.storage.vector_store_supa import SupabaseVectorStore
        SupabaseVectorStore(user_id).delete_chunks_for_document(source_file)
    except Exception as exc:
        st.warning(f"Could not remove vectors: {exc}")

    # 2. Remove from document registry
    try:
        from src.storage.registry_supa import SupabaseDocumentRegistry
        SupabaseDocumentRegistry(user_id).delete_document(source_file)
    except Exception as exc:
        st.warning(f"Could not remove registry entry: {exc}")

    # 3. Remove file from Supabase Storage
    if storage_path:
        try:
            from src.storage.file_store import delete_file
            delete_file(storage_path)
        except Exception:
            pass   # non-fatal

    st.success(f"✅ '{source_file}' removed.")


def _ingest_files_cloud(user_id: str, files: list, category: str) -> None:
    """Ingest already-uploaded files using the bytes we already have in memory.

    Parameters
    ----------
    user_id:  The visitor's UUID.
    files:    List of (UploadedFile, storage_path) tuples from the Streamlit uploader.
    category: 'lectures' | 'slides' | 'notes' | 'handwritten'
    """
    from src.ingestion.indexer import ingest_single_file_cloud

    status  = st.status("Indexing files…", expanded=True)
    results = []

    with status:
        for i, (f, storage_path) in enumerate(files):
            st.write(f"📄 **{f.name}** — parsing…")
            result = ingest_single_file_cloud(
                user_id=user_id,
                storage_path=storage_path,
                category=category,
                filename=f.name,
                file_bytes=f.getvalue(),   # pass bytes directly — skip re-download
            )
            results.append(result)

            if result.get("error") is None:
                st.write(
                    f"  ✅ {result['page_count']} pages · "
                    f"{result['chunk_count']} chunks indexed"
                )
            else:
                st.write(f"  ❌ Error: {result['error']}")

        if any(r.get("error") is None for r in results):
            status.update(label="✅ Indexing complete!", state="complete")
        else:
            status.update(label="❌ Indexing failed — see errors above", state="error")

    # Summary rows below the status box
    for r in results:
        ok    = r.get("error") is None
        badge = "cc-badge-ok" if ok else "cc-badge-err"
        label = (
            f"{r.get('page_count','?')} pages · {r.get('chunk_count','?')} chunks"
            if ok else f"Error: {r.get('error','')}"
        )
        st.markdown(
            f'<div class="cc-mat-row">'
            f'<span class="cc-mat-name">{r["source_file"]}</span>'
            f'<span class="cc-mat-meta">{label}</span>'
            f'<span class="{badge}">{"Indexed ✓" if ok else "Failed"}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    if any(r.get("error") is None for r in results):
        st.success("Go to **💬 Ask** to start querying your materials.")


def _ingest_files(paths: list[Path], category: str) -> None:
    """Ingest a specific list of newly-saved files into both indexes."""
    from src.ingestion.indexer import DocumentRegistry, BM25_PICKLE_PATH
    from src.retrieval.vector_store import VectorStore
    from src.retrieval.bm25_index import BM25Index
    from src.ingestion.chunker import chunk_all
    from src.config import PAGE_IMAGES_DIR

    registry = DocumentRegistry()   # uses local SQLite default path
    vs       = VectorStore()
    bm25     = BM25Index()
    if BM25_PICKLE_PATH.exists():
        try:
            bm25.load(BM25_PICKLE_PATH)
        except Exception:
            pass

    progress = st.progress(0)
    results  = []
    new_chunks: list = []

    for i, fpath in enumerate(paths):
        progress.progress((i + 1) / len(paths), text=f"Processing {fpath.name}...")
        try:
            pages = []
            fmt   = "unknown"

            if category == "lectures":
                from src.ingestion.pdf_parser import extract_pdf_pages
                pages = extract_pdf_pages(fpath, output_image_dir=PAGE_IMAGES_DIR)
                fmt = "pdf-lecture"
            elif category == "slides":
                from src.ingestion.pdf_parser import extract_slide_pages
                pages = extract_slide_pages(fpath, output_image_dir=PAGE_IMAGES_DIR)
                fmt = "pdf-slide"
            elif category == "notes":
                if fpath.suffix.lower() == ".md":
                    from src.ingestion.text_loader import load_markdown_file
                    pages = load_markdown_file(fpath)
                    fmt = "markdown"
                else:
                    from src.ingestion.text_loader import load_text_file
                    pages = load_text_file(fpath)
                    fmt = "text"
            elif category == "handwritten":
                from src.ingestion.ocr_pipeline import process_handwritten_image
                pages = process_handwritten_image(fpath, output_image_dir=PAGE_IMAGES_DIR)
                fmt = "handwritten"

            if not pages:
                results.append((fpath.name, "No pages extracted", False))
                continue

            chunks = chunk_all(pages, source=fpath.name)
            if not chunks:
                results.append((fpath.name, "No chunks produced", False))
                continue

            vs.add_chunks(chunks)
            new_chunks.extend(chunks)

            registry.register(
                source_file=fpath.name,
                format=fmt,
                page_count=len(pages),
                chunk_count=len(chunks),
                file_path=str(fpath),
            )
            results.append((fpath.name, f"{len(pages)} pages, {len(chunks)} chunks", True))

        except Exception as exc:
            results.append((fpath.name, f"Error: {exc}", False))

    # Rebuild BM25 with new chunks appended
    if new_chunks:
        bm25.add_chunks(new_chunks)
        BM25_PICKLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        bm25.save(BM25_PICKLE_PATH)

    progress.empty()

    for name, msg, ok in results:
        badge = "cc-badge-ok" if ok else "cc-badge-err"
        label = "Indexed" if ok else "Failed"
        st.markdown(
            f'<div class="cc-mat-row">'
            f'<span class="cc-mat-name">{name}</span>'
            f'<span class="cc-mat-meta">{msg}</span>'
            f'<span class="{badge}">{label}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    if any(ok for _, _, ok in results):
        st.success("Indexing complete. Go to Ask to start querying your materials.")
