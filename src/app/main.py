"""
Study Workspace — Streamlit main entry point.

Run with:
    streamlit run src/app/main.py
"""
import sys
import os
from pathlib import Path

# Add project root to path so `src.*` imports work
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

st.set_page_config(
    page_title="📚 Study Workspace",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Citation badges */
.citation-badge {
    background: #1a237e;
    color: white;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 0.75rem;
    font-family: monospace;
    margin: 0 2px;
    display: inline-block;
}
/* Refusal box */
.refusal-box {
    background: #fff3e0;
    border-left: 4px solid #ff6f00;
    padding: 12px 16px;
    border-radius: 4px;
    margin: 8px 0;
}
/* Evidence card */
.evidence-card {
    background: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 6px;
    padding: 10px 14px;
    margin: 6px 0;
    font-size: 0.9rem;
}
/* OCR warning */
.ocr-warning {
    background: #fff8e1;
    border-left: 3px solid #ffc107;
    padding: 8px 12px;
    font-size: 0.85rem;
    margin: 4px 0;
}
/* Confidence bar colours */
.high-conf { color: #2e7d32; }
.med-conf  { color: #f57f17; }
.low-conf  { color: #c62828; }
/* Pinned evidence */
.pinned-card {
    background: #e8f5e9;
    border-left: 4px solid #2e7d32;
    padding: 10px 14px;
    border-radius: 4px;
    margin: 6px 0;
}
</style>
""", unsafe_allow_html=True)

# ── Tab routing ───────────────────────────────────────────────────────────────
from src.app.ui_materials  import render_materials_tab
from src.app.ui_ask        import render_ask_tab
from src.app.ui_thread     import render_thread_tab
from src.app.ui_review     import render_review_tab
from src.app.ui_evaluation import render_evaluation_tab

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://em-content.zobj.net/source/apple/354/books_1f4da.png", width=60)
    st.title("Study Workspace")
    st.caption("Citation-first multi-document RAG")
    st.divider()

    # API key configuration
    api_key_env = os.environ.get("GEMINI_API_KEY", "")
    if not api_key_env:
        api_key_input = st.text_input(
            "🔑 Gemini API Key",
            type="password",
            help="Enter your Gemini API key. Will be stored in session only.",
            key="gemini_api_key_input",
        )
        if api_key_input:
            os.environ["GEMINI_API_KEY"] = api_key_input
            st.success("API key set ✓")
    else:
        st.success("API key loaded from .env ✓")

    st.divider()

    # Corpus status
    try:
        from src.retrieval.vector_store import get_vector_store
        vs = get_vector_store()
        n_chunks = vs.collection_size()
        if n_chunks > 0:
            st.metric("Indexed chunks", n_chunks)
        else:
            st.warning("No chunks indexed yet.\nGo to **Materials** tab to ingest corpus.")
    except Exception:
        st.warning("Vector store not ready. Install dependencies first.")

    st.divider()
    st.caption("💡 Tip: Start with **Materials** → ingest corpus → then **Ask**")

# ── Main tabs ─────────────────────────────────────────────────────────────────
tab_materials, tab_ask, tab_thread, tab_review, tab_eval = st.tabs([
    "📁 Materials", "💬 Ask", "🧵 Study Thread", "📋 Review", "📊 Evaluation"
])

with tab_materials:
    render_materials_tab()

with tab_ask:
    render_ask_tab()

with tab_thread:
    render_thread_tab()

with tab_review:
    render_review_tab()

with tab_eval:
    render_evaluation_tab()
