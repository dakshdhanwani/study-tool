"""
Page router — dispatches to the correct page based on st.session_state.page.
"""
from __future__ import annotations

import sys
from pathlib import Path
import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def render_ask_page() -> None:
    page = st.session_state.get("page", "ask")
    if page == "ask":
        _ask()
    elif page == "materials":
        _materials()
    elif page == "saved":
        _saved()
    elif page == "revision":
        _revision()
    elif page == "evaluation":
        _evaluation()


# ─────────────────────────────────────────────────────────────────────────────
# ASK  PAGE
# ─────────────────────────────────────────────────────────────────────────────

import re

_CIT = re.compile(r"\[([^\[\]]+?):(\d+|[A-Za-z][\w\-]*)\]")

def _chips(text: str, low: set[str] | None = None) -> str:
    low = low or set()
    def _r(m):
        s, p = m.group(1), m.group(2)
        cls = "chip chip-warn" if s.lower() in low else "chip"
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


def _run_query(q: str) -> None:
    """Run full RAG pipeline and store in session state."""
    try:
        from src.retrieval.vector_store import get_vector_store
        if get_vector_store().collection_size() == 0:
            st.warning("No documents indexed yet. Go to **📁 My Materials** and upload files first.")
            return

        from src.ingestion.indexer import load_index
        from src.retrieval.hybrid_search import hybrid_search
        from src.retrieval.reranker import get_reranker
        from src.generation.generator import generate_answer, configure_gemini
        from src.conversation.query_expander import expand_query

        mem = st.session_state.memory
        mgr = st.session_state.session_mgr

        history  = mem.get_history()
        expanded = expand_query(q, history, mgr.state)

        configure_gemini()
        vs, bm25 = load_index()
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


def _ask() -> None:
    result = st.session_state.result
    chunks = st.session_state.chunks
    query  = st.session_state.query

    # ── Two columns: answer | evidence ───────────────────────────────────────
    ans_col, ev_col = st.columns([1.75, 1.0], gap="large")

    # ──────────────── ANSWER COLUMN ──────────────────────────────────────────
    with ans_col:
        # Question bubble
        if query:
            st.markdown(f'<div class="q-bubble">{query}</div>', unsafe_allow_html=True)

        if result is None:
            st.markdown("""
            <div style="text-align:center;padding:60px 0;color:#9ba3b6">
              <div style="font-size:2.2rem">📘</div>
              <div style="font-size:1rem;font-weight:600;color:#4d5469;margin:10px 0 6px">
                Ask anything about your course materials
              </div>
              <div style="font-size:.85rem">
                Every answer is cited to the exact source page.<br>
                Unsupported questions are refused, not bluffed.
              </div>
            </div>""", unsafe_allow_html=True)
        else:
            _render_answer(result, chunks, query)

        st.markdown("---")

        # ── Action buttons ────────────────────────────────────────────────────
        if result and not result.is_refusal:
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("↗ Open source", use_container_width=True):
                    if chunks:
                        meta = chunks[0].get("metadata", chunks[0])
                        img  = meta.get("page_image_path", "")
                        if img and Path(img).exists():
                            st.session_state.preview_img = img
            with c2:
                if st.button("⊞ Save comparison", use_container_width=True):
                    st.session_state.session_mgr.add_to_comparison(
                        label=query[:40],
                        text=result.answer[:300],
                        source=", ".join({c.source_file for c in result.citations}),
                    )
                    st.toast("Added to comparison queue!")
            with c3:
                if st.button("📌 Pin for revision", use_container_width=True):
                    tid = st.session_state.memory.add_turn("assistant", result.answer,
                        citations=[{"src": c.source_file, "page": c.page_number}
                                    for c in result.citations])
                    st.session_state.memory.pin_turn(tid)
                    st.toast("Pinned!")

        # ── Page image preview ────────────────────────────────────────────────
        if "preview_img" in st.session_state:
            p = st.session_state.preview_img
            if p and Path(p).exists():
                with st.expander("📄 Source page", expanded=True):
                    st.image(p)
                    if st.button("✕ Close preview"):
                        del st.session_state.preview_img

        # ── Chat input ────────────────────────────────────────────────────────
        with st.form("chat", clear_on_submit=True):
            col_q, col_send = st.columns([5, 1])
            with col_q:
                user_q = st.text_input(
                    "question", label_visibility="collapsed",
                    placeholder="Ask another question about your course materials…",
                )
            with col_send:
                go = st.form_submit_button("→", use_container_width=True)
            if go and user_q.strip():
                with st.spinner("Searching & generating…"):
                    _run_query(user_q.strip())
                st.rerun()

    # ──────────────── EVIDENCE COLUMN ────────────────────────────────────────
    with ev_col:
        st.markdown(
            "<div style='font-size:1rem;font-weight:700;color:#1b2133'>Evidence</div>"
            "<div style='font-size:.75rem;color:#7c8499;margin-bottom:14px'>"
            "Pages from your course materials that support this answer.</div>",
            unsafe_allow_html=True,
        )

        if result is None:
            st.markdown(
                "<div style='color:#9ba3b6;font-size:.83rem;padding:20px 0'>"
                "Evidence cards appear here after you ask a question.</div>",
                unsafe_allow_html=True,
            )
        elif result.is_refusal:
            # Refusal card
            st.markdown(f"""
            <div class="refusal">
              <div class="refusal-title">⚠️ Not in your materials</div>
              <div class="refusal-body">{result.refusal_reason}</div>
              <div style="font-size:.75rem;color:#a16207;font-style:italic;margin-top:6px">
                "{query}"</div>
            </div>""", unsafe_allow_html=True)
        else:
            for i, chunk in enumerate(chunks[:5]):
                _evidence_card(chunk, i)

            # Grounding score
            s = result.grounding_score
            icon = "🟢" if s >= 0.8 else ("🟡" if s >= 0.5 else "🔴")
            st.markdown(
                f"<div style='font-size:.75rem;color:#7c8499;padding:8px 0'>"
                f"{icon} Grounding score: <b>{s:.0%}</b> "
                f"· {len(result.citations)} citation(s)</div>",
                unsafe_allow_html=True,
            )


def _render_answer(result, chunks, query) -> None:
    """Render structured answer with comparison table when applicable."""
    if result.is_refusal:
        st.markdown(f"""
        <div class="refusal">
          <div class="refusal-title">🚫 Not found in your materials</div>
          <div class="refusal-body">{result.refusal_reason}</div>
        </div>""", unsafe_allow_html=True)
        return

    low: set[str] = set()
    for c in chunks:
        meta = c.get("metadata", c)
        if float(meta.get("ocr_confidence", 1.0)) < 0.7:
            low.add(str(meta.get("source_file", "")).lower())

    paras = [p.strip() for p in re.split(r"\n{2,}", result.answer) if p.strip()]
    cmp   = _detect_compare(query + " " + result.answer[:200])

    for para in paras:
        # Section heading
        if re.match(r"^#{1,3}\s+", para):
            st.markdown(f'<div class="ans-h">{re.sub(r"^#{1,3}\s+","",para)}</div>',
                        unsafe_allow_html=True)
            continue
        if re.match(r"^\*\*[^*]+\*\*\s*$", para.strip()):
            st.markdown(f'<div class="ans-h">{para.strip().strip("*")}</div>',
                        unsafe_allow_html=True)
            continue
        st.markdown(f'<div class="ans-para">{_chips(para, low)}</div>',
                    unsafe_allow_html=True)

    # Comparison table
    if cmp:
        a, b = cmp
        rows = _comparison_rows(result.answer, a, b)
        if rows:
            st.markdown('<div class="ans-h">Comparison</div>', unsafe_allow_html=True)
            cells = "".join(
                f"<tr><td>{asp}</td>"
                f"<td>{_chips(at, low)}</td>"
                f"<td>{_chips(bt, low)}</td></tr>"
                for asp, at, bt in rows
            )
            st.markdown(
                f'<table class="cmp-table"><thead><tr>'
                f'<th>Aspect</th><th>{a}</th><th>{b}</th>'
                f'</tr></thead><tbody>{cells}</tbody></table>',
                unsafe_allow_html=True,
            )


def _evidence_card(chunk: dict, idx: int) -> None:
    meta  = chunk.get("metadata", chunk)
    src   = str(meta.get("source_file", "unknown"))
    page  = meta.get("page_number", "?")
    conf  = float(meta.get("ocr_confidence", 1.0))
    text  = (chunk.get("text") or "").strip()
    img_p = str(meta.get("page_image_path", chunk.get("page_image_path", "")))
    fmt   = str(meta.get("format", ""))
    excerpt = text[:140] + ("…" if len(text) > 140 else "")

    is_hw  = fmt in ("handwritten", "image-ocr") or "handwritten" in src.lower()
    is_low = conf < 0.75

    with st.container():
        st.markdown(f'<div class="ev-card">', unsafe_allow_html=True)
        
        # Header with Title and Page Badge
        st.markdown(
            f'<div class="ev-header">'
            f'<div class="ev-doc-title">{_friendly_name(src)}</div>'
            f'<div class="ev-page-badge">p. {page}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Page image thumbnail
        if img_p and Path(img_p).exists():
            st.image(img_p, use_container_width=True)

        # OCR badge
        if is_hw and is_low:
            st.markdown(f'<div class="ocr-badge">OCR {conf:.0%}</div>', unsafe_allow_html=True)

        st.markdown(f'<p class="ev-quote">"{excerpt}"</p>', unsafe_allow_html=True)

        if st.button("↗ Open source", key=f"ev_open_{idx}"):
            if img_p and Path(img_p).exists():
                st.session_state.preview_img = img_p
            else:
                st.toast(f"{src} · page {page}")

        st.markdown("</div>", unsafe_allow_html=True)


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
# MATERIALS  PAGE  (upload + ingest)
# ─────────────────────────────────────────────────────────────────────────────

def _materials() -> None:
    st.title("📁 My Materials")
    st.markdown(
        "Upload your actual lecture PDFs, slide decks, markdown notes, "
        "and **photos of handwritten notes**. The workspace will OCR, chunk, "
        "and index everything so you can ask questions over it."
    )

    # ── Upload section ────────────────────────────────────────────────────────
    with st.container(border=True):
        st.subheader("Upload files")
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
            allowed = ext_map[doc_type]
            category = cat_map[doc_type]

            uploaded = st.file_uploader(
                "Drop files here or click to browse",
                type=allowed,
                accept_multiple_files=True,
                label_visibility="collapsed",
            )

        if uploaded:
            dest_dir = PROJECT_ROOT / "corpus" / category
            dest_dir.mkdir(parents=True, exist_ok=True)

            st.markdown(f"**{len(uploaded)} file(s) selected:**")
            saved_paths = []
            for f in uploaded:
                dest = dest_dir / f.name
                dest.write_bytes(f.getvalue())
                saved_paths.append(dest)
                st.markdown(
                    f'<div class="file-row">'
                    f'<span class="fname">{f.name}</span>'
                    f'<span class="fmeta">{f.size/1024:.1f} KB · {category}</span>'
                    f'<span class="badge-ok">Saved ✓</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            st.markdown("")
            if st.button("🚀 Index uploaded files", type="primary", use_container_width=True):
                _ingest_files(saved_paths, category)

    st.markdown("")

    # ── Already indexed ───────────────────────────────────────────────────────
    with st.container(border=True):
        st.subheader("Indexed documents")

        try:
            from src.ingestion.indexer import DocumentRegistry
            from src.config import SQLITE_PATH
            docs = DocumentRegistry(SQLITE_PATH).list_documents()
        except Exception:
            docs = []

        if not docs:
            st.info(
                "No documents indexed yet. Upload files above and click **Index uploaded files**, "
                "or use the synthetic corpus below."
            )
        else:
            fmt_icon = {"pdf-lecture":"📄","pdf-slide":"📊","markdown":"📝",
                        "text":"📄","handwritten":"✍️","image-ocr":"✍️"}
            for doc in docs:
                icon = fmt_icon.get(doc.get("format",""),"📄")
                c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                c1.markdown(f"{icon} **{doc['source_file']}**")
                c2.caption(f"{doc.get('page_count','?')} pages")
                c3.caption(f"{doc.get('chunk_count','?')} chunks")
                c4.caption(doc.get('ingested_at','')[:10])

    st.markdown("")

    # ── Synthetic corpus (fallback) ───────────────────────────────────────────
    with st.expander("🧪 Use synthetic demo corpus (no real files needed)", expanded=False):
        st.markdown(
            "Generates a fake 60-page Algorithms & Data Structures course — "
            "useful for testing the app before you upload real materials."
        )
        force = st.checkbox("Force re-generate")
        if st.button("Generate demo corpus"):
            with st.spinner("Generating…"):
                import subprocess, sys as _sys
                r = subprocess.run(
                    [_sys.executable, "corpus/generate_corpus.py"],
                    capture_output=True, text=True, cwd=str(PROJECT_ROOT)
                )
                if r.returncode == 0:
                    st.success("Demo corpus generated!")
                else:
                    st.error(r.stderr[-500:])

        if st.button("🚀 Ingest demo corpus", type="primary"):
            with st.spinner("Ingesting all corpus files…"):
                from src.ingestion.indexer import ingest_corpus
                from src.config import CORPUS_DIR
                summary = ingest_corpus(CORPUS_DIR, force_reingest=force)
            st.success(f"Done — {summary['total_documents']} docs, {summary['total_chunks']} chunks")
            if summary["errors"]:
                for e in summary["errors"]:
                    st.error(e)
            st.rerun()


def _ingest_files(paths: list[Path], category: str) -> None:
    """Ingest a specific list of newly-saved files into both indexes."""
    from src.ingestion.indexer import DocumentRegistry, BM25_PICKLE_PATH
    from src.retrieval.vector_store import VectorStore
    from src.retrieval.bm25_index import BM25Index
    from src.ingestion.chunker import chunk_all
    from src.config import SQLITE_PATH, PAGE_IMAGES_DIR

    registry = DocumentRegistry(SQLITE_PATH)
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
        badge = "badge-ok" if ok else "badge-err"
        label = "Indexed" if ok else "Failed"
        st.markdown(
            f'<div class="file-row">'
            f'<span class="fname">{name}</span>'
            f'<span class="fmeta">{msg}</span>'
            f'<span class="{badge}">{label}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    if any(ok for _, _, ok in results):
        st.success("Indexing complete. Go to Ask to start querying your materials.")


# ─────────────────────────────────────────────────────────────────────────────
# SAVED / REVISION / EVALUATION  (lightweight)
# ─────────────────────────────────────────────────────────────────────────────

def _saved() -> None:
    st.title("🔖 Saved Answers")
    mem    = st.session_state.memory
    pinned = mem.get_pinned()
    if not pinned:
        st.info("No pinned answers yet. Use **📌 Pin for revision** after any answer.")
        return
    for p in pinned:
        with st.expander(p["content"][:60] + "…"):
            st.markdown(_chips(p["content"]), unsafe_allow_html=True)
            st.caption(p["timestamp"][:19])
            if st.button("Unpin", key=f"unpin_{p['id']}"):
                mem.unpin_turn(p["id"])
                st.rerun()


def _revision() -> None:
    st.title("📋 Revision")
    mgr   = st.session_state.session_mgr
    cards = mgr.state.concept_cards

    with st.form("new_card"):
        st.subheader("Save a concept card")
        title = st.text_input("Concept name")
        defn  = st.text_area("Definition / key points", height=80)
        srcs  = st.text_input("Sources (comma-separated)")
        if st.form_submit_button("Save card") and title:
            mgr.save_concept_card(
                title, defn,
                [s.strip() for s in srcs.split(",") if s.strip()]
            )
            st.success("Saved!")
            st.rerun()

    st.divider()
    if not cards:
        st.info("No cards yet.")
    else:
        cols = st.columns(2)
        for i, card in enumerate(cards):
            with cols[i % 2]:
                with st.container(border=True):
                    st.markdown(f"**{card['title']}**")
                    st.markdown(card.get("definition",""))
                    if card.get("sources"):
                        st.caption(", ".join(card["sources"]))


def _evaluation() -> None:
    import json
    st.title("📊 Evaluation")
    st.markdown(
        "Run the **30-question benchmark** (10 single-doc · 10 multi-doc · 10 unanswerable). "
        "The app grades itself automatically."
    )
    eval_path = PROJECT_ROOT / "evaluation" / "questions.json"

    if not eval_path.exists():
        st.info("Evaluation questions not generated yet.")
        if st.button("Generate 30-question set"):
            # Import the generator from ui_evaluation
            from src.app.ui_evaluation import _generate_questions
            _generate_questions(eval_path)
            st.rerun()
        return

    with open(eval_path) as f:
        qs = json.load(f)

    c1, c2, c3 = st.columns(3)
    c1.metric("Single-doc",   sum(1 for q in qs if q["type"]=="single_doc"))
    c2.metric("Multi-doc",    sum(1 for q in qs if q["type"]=="multi_doc"))
    c3.metric("Unanswerable", sum(1 for q in qs if q["type"]=="unanswerable"))

    subset = st.selectbox("Run subset", ["All 30", "Single-doc", "Multi-doc", "Unanswerable"])
    map_   = {"All 30": qs,
               "Single-doc":   [q for q in qs if q["type"]=="single_doc"],
               "Multi-doc":    [q for q in qs if q["type"]=="multi_doc"],
               "Unanswerable": [q for q in qs if q["type"]=="unanswerable"]}

    if st.button("▶ Run Evaluation", type="primary"):
        from src.app.ui_evaluation import _run_eval, _show_results
        results_dir = PROJECT_ROOT / "evaluation" / "results"
        with st.spinner(f"Running {len(map_[subset])} questions…"):
            results = _run_eval(map_[subset])
        if results:
            _show_results(results, results_dir)
