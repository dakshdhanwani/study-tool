"""
Course Companion — main entry point (clean rebuild).

Run with:
    streamlit run src/app/main.py
"""
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

st.set_page_config(
    page_title="Course Companion",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Load .env ──────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except Exception:
    pass

# ── Global CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Hide default Streamlit chrome */
#MainMenu, footer { visibility: hidden !important; height: 0 !important; }
.block-container { padding: 1.5rem 1rem 1rem 1rem !important; max-width: 100% !important; }

/* Sidebar overrides */
[data-testid="stSidebar"] { border-right: none !important; }
[data-testid="stSidebar"] * { color: #8a92a8; }
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { color: #ffffff !important; }
[data-testid="stSidebar"] hr { border-color: #2d3347 !important; margin: 15px 0 !important; }

/* Right column background (Evidence panel) */
[data-testid="column"]:nth-of-type(2) {
    background-color: #f8f9fa;
    padding: 1.5rem;
    border-radius: 12px;
    border-left: 1px solid #edf0f5;
    height: calc(100vh - 40px);
    overflow-y: auto;
}

/* Citation chips */
.chip {
    display: inline-block; background: #eef2ff; color: #3730a3;
    border: 1px solid #c7d2fe; border-radius: 12px;
    padding: 2px 10px; font-size: 0.72rem; font-weight: 600;
    margin: 0 4px 4px 0; white-space: nowrap; cursor: pointer;
}
.chip-warn { background: #fef3c7; color: #92400e; border-color: #fcd34d; }

/* Question bubble */
.q-bubble {
    background: #eef2ff; border-radius: 20px; padding: 14px 28px;
    text-align: center; font-size: 1rem; color: #1e1b4b;
    margin: 0 auto 28px; max-width: 600px; font-weight: 500;
}

/* Answer formatting */
.ans-para { font-size: 0.95rem; color: #334155; line-height: 1.7; margin-bottom: 16px; }
.ans-h    { font-size: 1.1rem; font-weight: 700; color: #0f172a; margin: 24px 0 12px; }

/* Comparison table */
.cmp-table { width: 100%; border-collapse: collapse; font-size: 0.88rem; margin: 16px 0 24px; border-radius: 8px; overflow: hidden; border: 1px solid #e2e8f0; }
.cmp-table th { background: #f1f5f9; color: #475569; padding: 12px 16px; text-align: left; font-weight: 600; border-bottom: 1px solid #e2e8f0; }
.cmp-table td { padding: 12px 16px; border-bottom: 1px solid #f1f5f9; vertical-align: top; color: #334155; }
.cmp-table td:first-child { font-weight: 600; color: #0f172a; width: 25%; background: #f8fafc; }

/* Evidence cards */
.ev-card {
    background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px;
    padding: 16px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.02);
}
.ev-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; }
.ev-doc-title { font-weight: 700; color: #0f172a; font-size: 0.85rem; }
.ev-page-badge { background: #64748b; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.7rem; font-weight: 600; }
.ev-quote { border-left: 3px solid #cbd5e1; padding-left: 12px; color: #475569; font-style: italic; font-size: 0.8rem; line-height: 1.5; margin: 8px 0 14px; }
.ocr-badge { display: inline-block; background: #f59e0b; color: white; border-radius: 4px; padding: 2px 8px; font-size: 0.7rem; font-weight: 700; margin-bottom: 8px; }

/* Refusal box */
.refusal { background: #fffbeb; border: 1px solid #fcd34d; border-radius: 12px; padding: 16px 20px; margin: 16px 0; }
.refusal-title { font-weight: 700; color: #b45309; margin-bottom: 8px; }
.refusal-body  { font-size: 0.9rem; color: #78350f; line-height: 1.5; }

/* File status rows */
.file-row { display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-radius: 8px; margin-bottom: 8px; background: #f8fafc; border: 1px solid #e2e8f0; font-size: 0.85rem; }
.file-row .fname { flex: 1; color: #0f172a; font-weight: 600; }
.file-row .fmeta { color: #64748b; font-size: 0.8rem; }
.badge-ok   { background: #dcfce7; color: #166534; border-radius: 6px; padding: 2px 8px; font-size: 0.72rem; font-weight: 600; }
.badge-err  { background: #fee2e2; color: #991b1b; border-radius: 6px; padding: 2px 8px; font-size: 0.72rem; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ── Session state bootstrap ────────────────────────────────────────────────────
if "memory" not in st.session_state:
    from src.conversation.memory import ConversationMemory
    st.session_state.memory = ConversationMemory()
if "session_mgr" not in st.session_state:
    from src.conversation.session import SessionManager
    st.session_state.session_mgr = SessionManager(st.session_state.memory)
if "result"  not in st.session_state: st.session_state.result  = None
if "chunks"  not in st.session_state: st.session_state.chunks  = []
if "query"   not in st.session_state: st.session_state.query   = ""
if "history" not in st.session_state: st.session_state.history = []

# ── Render app ─────────────────────────────────────────────────────────────────
from src.app.sidebar  import render_sidebar
from src.app.page_ask import render_ask_page

render_sidebar()
render_ask_page()
