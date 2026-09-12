"""
Right panel — evidence cards with page images, OCR badges, refusal card.
"""
from __future__ import annotations

import sys
from pathlib import Path
import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _short_doc_name(source_file: str) -> tuple[str, str]:
    """Return (short_title, subtitle) for display on evidence card."""
    name = Path(source_file).stem

    # Map synthetic filenames to readable names
    mapping = {
        "lecture_01_basics":  ("Data Structures Basics",  "Lecture 01"),
        "lecture_02_trees":   ("Trees & Heaps",            "Lecture 02"),
        "lecture_03_sorting": ("Sorting Algorithms",       "Lecture 03"),
        "slides_01_overview": ("Algorithm Overview",       "Lecture 05 · Slides"),
        "slides_02_advanced": ("Advanced Topics",          "Lecture 06 · Slides"),
        "study_notes":        ("Study Notes",              "Markdown"),
        "handwritten_clean":  ("My Notes",                 "Handwritten photo 1"),
        "handwritten_hard":   ("Maya's notes",             "photo 2"),
    }
    for key, (title, sub) in mapping.items():
        if key in name.lower():
            return title, sub

    # Generic fallback
    readable = name.replace("_", " ").title()
    return readable, source_file


def _render_evidence_card(chunk: dict, idx: int) -> None:
    """Render a single evidence card with optional page image thumbnail."""
    meta  = chunk.get("metadata", chunk)
    src   = str(meta.get("source_file", chunk.get("source_file", "unknown")))
    page  = meta.get("page_number", chunk.get("page_number", "?"))
    conf  = float(meta.get("ocr_confidence", chunk.get("ocr_confidence", 1.0)))
    text  = (chunk.get("text") or "").strip()
    img_p = str(meta.get("page_image_path", chunk.get("page_image_path", "")))

    title, subtitle = _short_doc_name(src)
    excerpt = text[:160].strip()
    if len(text) > 160:
        excerpt += "…"

    is_low_conf = conf < 0.75
    is_handwritten = "handwritten" in src.lower() or meta.get("format", "") == "handwritten"

    # ── Card HTML header ───────────────────────────────────────────────────────
    # Page image / thumbnail
    if img_p and Path(img_p).exists():
        # Render image
        st.markdown(f"""
        <div class="cc-ecard">
          <div class="cc-ecard-top">
        """, unsafe_allow_html=True)

        col_img, col_meta = st.columns([0.38, 0.62])
        with col_img:
            st.image(img_p, use_container_width=True)
            if is_handwritten and is_low_conf:
                st.markdown(
                    f'<div class="cc-ecard-ocr-badge">OCR {conf:.0%}</div>',
                    unsafe_allow_html=True
                )
            st.markdown(
                f'<div class="cc-ecard-page-badge">p. {page}</div>',
                unsafe_allow_html=True
            )
        with col_meta:
            st.markdown(f"""
            <div style="padding:10px 8px">
              <div class="cc-ecard-doc">{title}</div>
              <div class="cc-ecard-page">{subtitle}<br>p. {page}</div>
              <blockquote class="cc-ecard-quote">"{excerpt}"</blockquote>
            </div>
            """, unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

    else:
        # No image available — text-only card
        st.markdown(f"""
        <div class="cc-ecard">
          <div style="padding:12px 14px">
            <div class="cc-ecard-doc">{title}</div>
            <div class="cc-ecard-page">{subtitle} · p. {page}</div>
            {"" if not is_low_conf else
             f'<div style="display:inline-block;background:#fef3c7;color:#92400e;'
             f'border-radius:5px;padding:2px 7px;font-size:.68rem;font-weight:700;margin:4px 0">'
             f'OCR {conf:.0%}</div>'}
            <blockquote class="cc-ecard-quote" style="margin-top:6px">"{excerpt}"</blockquote>
          </div>
        """, unsafe_allow_html=True)

    # ── Open source button ─────────────────────────────────────────────────────
    if st.button("↗ Open source", key=f"opensrc_{idx}_{src}_{page}"):
        if img_p and Path(img_p).exists():
            st.session_state.preview_image = img_p
        else:
            st.toast(f"{src} — page {page} (no image rendered yet)")

    st.markdown('</div>', unsafe_allow_html=True)  # close cc-ecard


def _render_refusal_card(result) -> None:
    """Render the amber refusal card shown below evidence."""
    query = st.session_state.get("current_query", "")
    st.markdown(f"""
    <div class="cc-refusal">
      <div class="cc-refusal-title">⚠️ I can't find support for this in your course materials.</div>
      <div class="cc-refusal-body">{result.refusal_reason}</div>
      <div class="cc-refusal-q">"{query}"</div>
    </div>
    """, unsafe_allow_html=True)


def render_right_panel() -> None:
    result = st.session_state.get("current_result")
    chunks = st.session_state.get("current_chunks", [])

    st.markdown("""
    <div style="background:#fafbff;padding:18px 4px 0">
      <div class="cc-evidence-title">Evidence</div>
      <div class="cc-evidence-sub">Pages from your course materials that support this answer.</div>
    </div>
    """, unsafe_allow_html=True)

    if result is None:
        st.markdown("""
        <div style="text-align:center;padding:40px 10px;color:#9ba3b6;font-size:.82rem">
            Evidence cards will appear here once you ask a question.
        </div>""", unsafe_allow_html=True)
        return

    # ── Evidence cards ─────────────────────────────────────────────────────────
    if not result.is_refusal and chunks:
        for i, chunk in enumerate(chunks[:4]):   # show top 4
            _render_evidence_card(chunk, i)
            st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)

    elif result.is_refusal:
        st.markdown("""
        <div style="text-align:center;padding:30px 10px;color:#9ba3b6;font-size:.82rem">
            No supporting evidence found.
        </div>""", unsafe_allow_html=True)

    # ── Refusal card ───────────────────────────────────────────────────────────
    if result.is_refusal:
        _render_refusal_card(result)

    # ── Grounding score ────────────────────────────────────────────────────────
    if not result.is_refusal and result.citations:
        score = result.grounding_score
        icon  = "🟢" if score >= 0.8 else ("🟡" if score >= 0.5 else "🔴")
        st.markdown(f"""
        <div style="background:#f4f5f7;border-radius:8px;padding:10px 14px;margin-top:8px;
            font-size:.78rem;color:#4d5469">
          {icon} <strong>Grounding score:</strong> {score:.0%}
          &nbsp;·&nbsp; {len(result.citations)} citation(s)
        </div>
        """, unsafe_allow_html=True)
