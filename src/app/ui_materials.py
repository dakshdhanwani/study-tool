"""
Materials tab: corpus upload, OCR processing, source viewer.
"""
from __future__ import annotations

import sys
from pathlib import Path
import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def render_materials_tab():
    st.header("📁 Course Materials")
    st.markdown("Upload and manage your course documents. Ingest them to enable grounded Q&A.")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Corpus Ingestion")

        corpus_dir = PROJECT_ROOT / "corpus"
        if not corpus_dir.exists():
            st.warning("No `corpus/` directory found. Run `python corpus/generate_corpus.py` first.")
            return

        # Show corpus files
        files_found = []
        for pattern in ["lectures/*.pdf", "slides/*.pdf", "notes/*.md", "notes/*.txt",
                         "handwritten/*.png", "handwritten/*.jpg", "handwritten/*.jpeg",
                         "lectures/*.txt", "slides/*.txt", "handwritten/*.txt"]:
            files_found.extend(corpus_dir.glob(pattern))

        if not files_found:
            st.info("No documents found in corpus/. Run `python corpus/generate_corpus.py` to generate the synthetic corpus.")
        else:
            st.markdown(f"**{len(files_found)} files found in corpus:**")

            format_icons = {".pdf": "📄", ".md": "📝", ".txt": "📄",
                           ".png": "🖼️", ".jpg": "🖼️", ".jpeg": "🖼️"}
            format_labels = {"lectures": "Lecture", "slides": "Slides",
                             "notes": "Notes", "handwritten": "Handwritten"}

            # Group by folder
            by_folder: dict[str, list] = {}
            for f in sorted(files_found):
                folder = f.parent.name
                by_folder.setdefault(folder, []).append(f)

            for folder, files in by_folder.items():
                label = format_labels.get(folder, folder)
                with st.expander(f"{label} ({len(files)} files)", expanded=True):
                    for f in files:
                        icon = format_icons.get(f.suffix.lower(), "📄")
                        size_kb = f.stat().st_size / 1024
                        st.markdown(f"{icon} `{f.name}` — {size_kb:.1f} KB")

        st.divider()

        col_a, col_b = st.columns(2)
        with col_a:
            force = st.checkbox("Force re-ingest all files", value=False,
                                help="Re-process files even if already ingested.")
        with col_b:
            if st.button("🚀 Run Ingestion", type="primary", use_container_width=True):
                with st.spinner("Ingesting corpus... This may take a few minutes for OCR."):
                    try:
                        from src.ingestion.indexer import ingest_corpus
                        summary = ingest_corpus(force_reingest=force)

                        st.success(f"✅ Ingestion complete!")
                        col_m1, col_m2, col_m3 = st.columns(3)
                        col_m1.metric("Documents", summary["total_documents"])
                        col_m2.metric("Chunks", summary["total_chunks"])
                        col_m3.metric("Formats", len(summary["formats_found"]))

                        if summary["errors"]:
                            with st.expander(f"⚠️ {len(summary['errors'])} errors"):
                                for e in summary["errors"]:
                                    st.error(e)

                    except Exception as exc:
                        st.error(f"Ingestion failed: {exc}")
                        import traceback
                        st.code(traceback.format_exc())

    with col2:
        st.subheader("Document Registry")
        try:
            from src.ingestion.indexer import DocumentRegistry
            from src.config import SQLITE_PATH
            registry = DocumentRegistry(SQLITE_PATH)
            docs = registry.list_documents()

            if not docs:
                st.info("No documents ingested yet.")
            else:
                for doc in docs:
                    with st.container():
                        fmt_icon = {"pdf-lecture": "📄", "pdf-slide": "📊",
                                    "markdown": "📝", "text": "📄",
                                    "handwritten": "🖼️", "image-ocr": "🖼️"}.get(doc["format"], "📄")
                        st.markdown(
                            f"{fmt_icon} **{doc['source_file']}**  \n"
                            f"  {doc['page_count']} pages · {doc['chunk_count']} chunks  \n"
                            f"  *{doc['ingested_at'][:10]}*"
                        )
                        st.divider()
        except Exception as exc:
            st.info(f"Registry not available yet: {exc}")

    # ── Source viewer ──────────────────────────────────────────────────────────
    st.divider()
    st.subheader("🔍 Source Viewer")
    st.markdown("Preview extracted text and page images for any ingested document.")

    try:
        from src.retrieval.vector_store import get_vector_store
        vs = get_vector_store()
        if vs.collection_size() == 0:
            st.info("Ingest the corpus first to browse sources.")
            return

        # Search within corpus
        preview_query = st.text_input("Search for a passage to preview:", key="source_preview_query")
        if preview_query:
            results = vs.search(preview_query, top_k=5)
            for i, r in enumerate(results):
                meta = r.get("metadata", {})
                confidence = float(meta.get("ocr_confidence", 1.0))
                conf_class = "high-conf" if confidence >= 0.8 else ("med-conf" if confidence >= 0.6 else "low-conf")
                conf_label = f"{confidence:.0%}"

                with st.expander(
                    f"📄 {meta.get('source_file','?')} — Page {meta.get('page_number','?')} "
                    f"[similarity: {r['score']:.2f}]"
                ):
                    # OCR warning
                    if confidence < 0.7:
                        st.markdown(
                            f'<div class="ocr-warning">⚠️ Low OCR confidence: '
                            f'<span class="{conf_class}">{conf_label}</span>. '
                            f'Verify against original image.</div>',
                            unsafe_allow_html=True
                        )

                    # Text content
                    st.markdown("**Extracted text:**")
                    st.markdown(f'<div class="evidence-card">{r["text"]}</div>',
                                unsafe_allow_html=True)

                    # Page image preview if available
                    img_path = meta.get("page_image_path", "")
                    if img_path and Path(img_path).exists():
                        st.markdown("**Page image:**")
                        st.image(img_path, caption=f"{meta.get('source_file')} — Page {meta.get('page_number')}")

                    st.caption(f"Format: {meta.get('format','?')} | "
                               f"OCR: {conf_label} | "
                               f"Section: {meta.get('section_title','—')}")

    except Exception as exc:
        st.error(f"Source viewer error: {exc}")
