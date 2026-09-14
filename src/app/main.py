"""
Course Companion — main entry point.

Run with:
    streamlit run src/app/main.py
"""
import sys
import os
import uuid
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

# ── Global CSS Design System ───────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Reset Streamlit chrome ──────────────────────────────────────────────── */
#MainMenu, footer { visibility: hidden !important; height: 0 !important; }
.block-container { padding-left: 1rem !important; padding-right: 1rem !important; padding-bottom: 2rem !important; max-width: 100% !important; }

/* ── Sidebar — dark navy ─────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background-color: #1b2133 !important;
    border-right: 1px solid #252d45 !important;
}
[data-testid="stSidebar"] > div:first-child { padding: 0 !important; }
[data-testid="stSidebar"] * { color: #8a93b0; }
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 { color: #ffffff !important; }
[data-testid="stSidebar"] hr { border-color: #252d45 !important; margin: 8px 0 !important; }
[data-testid="stSidebar"] small { color: #5d6580 !important; }
[data-testid="stSidebar"] code { background: #252d45 !important; color: #a0a9c2 !important; border: none !important; }
[data-testid="stSidebar"] .stCaption { color: #4d5469 !important; font-size: 0.72rem !important; }

/* Sidebar nav buttons */
[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    border: none !important;
    color: #8a93b0 !important;
    text-align: left !important;
    font-size: 0.87rem !important;
    font-weight: 500 !important;
    padding: 8px 14px !important;
    border-radius: 8px !important;
    width: 100% !important;
    transition: background 0.15s, color 0.15s !important;
    margin-bottom: 2px !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: #252d45 !important;
    color: #e2e8f0 !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: #252d45 !important;
    color: #ffffff !important;
    border-left: 3px solid #3b5bdb !important;
    padding-left: 11px !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
    background: #2d3a5e !important;
}

/* Sidebar text input */
[data-testid="stSidebar"] .stTextInput input {
    background: #252d45 !important;
    border-color: #3d4456 !important;
    color: #e2e8f0 !important;
    font-size: 0.83rem !important;
}
[data-testid="stSidebar"] .stTextInput label { color: #8a93b0 !important; font-size: 0.78rem !important; }
[data-testid="stSidebar"] .stWarning { background: #2d2510 !important; border-color: #7c5c00 !important; }

/* ── Question bubble ─────────────────────────────────────────────────────── */
.cc-question-bubble {
    background: #eef2ff;
    border-radius: 10px;
    padding: 12px 18px;
    font-size: 0.95rem;
    font-weight: 600;
    color: #1e2330;
    margin-bottom: 20px;
    border-left: 3px solid #3b5bdb;
    max-width: 700px;
}

/* ── Answer typography ───────────────────────────────────────────────────── */
.cc-para {
    font-size: 0.92rem;
    color: #2d3347;
    line-height: 1.72;
    margin-bottom: 14px;
}
.cc-section-h {
    font-size: 1rem;
    font-weight: 700;
    color: #1e2330;
    margin: 20px 0 10px;
    padding-bottom: 5px;
    border-bottom: 1px solid #e8edf5;
}

/* ── Citation chips ──────────────────────────────────────────────────────── */
.cc-chip {
    display: inline-flex;
    align-items: center;
    background: #eff6ff;
    color: #2563eb;
    border: 1px solid #bfdbfe;
    border-radius: 6px;
    padding: 1px 8px;
    font-size: 0.72rem;
    font-weight: 700;
    margin: 0 3px 3px 0;
    white-space: nowrap;
    cursor: pointer;
    font-family: ui-monospace, monospace;
}
.cc-chip:hover { background: #dbeafe; border-color: #93c5fd; }
.cc-chip.low {
    background: #fffbeb;
    color: #b45309;
    border-color: #fcd34d;
}

/* ── Sources strip ───────────────────────────────────────────────────────── */
.cc-sources-row {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    padding: 10px 0 6px;
    border-top: 1px solid #f1f5f9;
    margin-top: 6px;
}
.cc-sources-label {
    font-size: 0.77rem;
    font-weight: 700;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}

/* ── Comparison table ────────────────────────────────────────────────────── */
.cc-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.84rem;
    margin: 14px 0 20px;
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #e2e8f0;
}
.cc-table thead { background: #f8fafc; }
.cc-table th {
    text-align: left;
    padding: 10px 14px;
    font-weight: 700;
    color: #475569;
    border-bottom: 1px solid #e2e8f0;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.cc-table td {
    padding: 10px 14px;
    border-bottom: 1px solid #f1f5f9;
    vertical-align: top;
    color: #334155;
    line-height: 1.55;
}
.cc-table tr:last-child td { border-bottom: none; }
.cc-table td:first-child {
    font-weight: 600;
    color: #1e2330;
    width: 22%;
    background: #f8fafc;
}

/* ── Grounding status ────────────────────────────────────────────────────── */
.cc-grounding-ok {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 10px;
    padding: 10px 14px;
    margin: 14px 0 8px;
    font-size: 0.82rem;
    color: #166534;
}
.cc-grounding-warn {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    background: #fffbeb;
    border: 1px solid #fde68a;
    border-radius: 10px;
    padding: 10px 14px;
    margin: 14px 0 8px;
    font-size: 0.82rem;
    color: #92400e;
}
.cc-grounding-text strong { display: block; font-weight: 700; margin-bottom: 2px; }

/* ── Refusal box ─────────────────────────────────────────────────────────── */
.cc-refusal {
    background: #fffbeb;
    border: 1.5px solid #fcd34d;
    border-radius: 12px;
    padding: 18px 22px;
    margin: 16px 0;
}
.cc-refusal-title {
    font-weight: 700;
    color: #b45309;
    font-size: 0.95rem;
    margin-bottom: 8px;
}
.cc-refusal-body {
    font-size: 0.88rem;
    color: #78350f;
    line-height: 1.6;
    margin-bottom: 10px;
}
.cc-refusal-q {
    font-size: 0.79rem;
    color: #a16207;
    font-style: italic;
    border-top: 1px solid #fde68a;
    padding-top: 8px;
}

/* ── Evidence panel header ───────────────────────────────────────────────── */
.cc-ev-title {
    font-size: 0.97rem;
    font-weight: 700;
    color: #1b2133;
    margin-bottom: 2px;
}
.cc-ev-sub {
    font-size: 0.74rem;
    color: #7c8499;
    margin-bottom: 10px;
}

/* ── Primary evidence card ───────────────────────────────────────────────── */
.cc-ecard-primary {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    overflow: hidden;
    margin-bottom: 14px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
.cc-ecard-hdr {
    display: flex;
    align-items: center;
    padding: 10px 14px 8px;
    gap: 8px;
}
.cc-ecard-doc-title {
    font-weight: 700;
    font-size: 0.84rem;
    color: #1e2330;
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.cc-ecard-doc-sub { font-size: 0.71rem; color: #6b7280; }
.cc-ecard-page-badge {
    background: #334155;
    color: #ffffff;
    border-radius: 8px;
    padding: 2px 9px;
    font-size: 0.71rem;
    font-weight: 700;
    flex-shrink: 0;
}
.cc-ecard-quote {
    font-size: 0.78rem;
    color: #475569;
    font-style: italic;
    border-left: 3px solid #cbd5e1;
    margin: 6px 14px 12px;
    padding-left: 10px;
    line-height: 1.55;
}

/* ── OCR warning badge ───────────────────────────────────────────────────── */
.cc-ocr-badge {
    display: inline-block;
    background: #fef3c7;
    color: #92400e;
    border-radius: 5px;
    padding: 2px 9px;
    font-size: 0.7rem;
    font-weight: 700;
    margin: 2px 14px 8px;
}
.cc-ocr-warning {
    background: #fffbeb;
    border: 1px solid #fde68a;
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 0.78rem;
    color: #92400e;
    margin: 4px 0 8px;
}

/* ── Also cited / secondary cards ───────────────────────────────────────── */
.cc-also-label {
    font-size: 0.75rem;
    font-weight: 700;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin: 12px 0 8px;
}
.cc-ecard-sec {
    background: #ffffff;
    border: 1px solid #e8edf5;
    border-radius: 10px;
    overflow: hidden;
    margin-bottom: 10px;
}
.cc-ecard-sec-info { padding: 8px 12px 4px; }
.cc-ecard-sec-title { font-weight: 700; font-size: 0.79rem; color: #1e2330; }
.cc-ecard-sec-page { font-size: 0.7rem; color: #6b7280; margin-bottom: 4px; }
.cc-ecard-sec-quote {
    font-size: 0.74rem; color: #64748b; font-style: italic;
    border-left: 2px solid #e2e8f0; padding: 2px 0 2px 8px; margin: 4px 12px 8px;
    line-height: 1.45;
}

/* ── Materials page ──────────────────────────────────────────────────────── */
.cc-mat-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 11px 16px;
    border-radius: 8px;
    margin-bottom: 6px;
    background: #f8fafc;
    border: 1px solid #e8edf5;
    font-size: 0.85rem;
}
.cc-mat-name { flex: 1; font-weight: 600; color: #1e2330; }
.cc-mat-meta { color: #6b7280; font-size: 0.78rem; min-width: 80px; text-align: right; }
.cc-badge-ok {
    background: #dcfce7; color: #166534;
    border-radius: 6px; padding: 2px 9px; font-size: 0.71rem; font-weight: 700;
}
.cc-badge-err {
    background: #fee2e2; color: #991b1b;
    border-radius: 6px; padding: 2px 9px; font-size: 0.71rem; font-weight: 700;
}

/* ── Saved cards ─────────────────────────────────────────────────────────── */
.cc-saved-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 14px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.03);
}
.cc-saved-title { font-weight: 700; color: #1e2330; font-size: 0.9rem; margin-bottom: 6px; }
.cc-saved-body { font-size: 0.83rem; color: #475569; line-height: 1.55; margin-bottom: 10px; }
.cc-saved-ts { font-size: 0.71rem; color: #9ca3af; }

/* ── Revision cards ──────────────────────────────────────────────────────── */
.cc-rev-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 16px 18px;
    margin-bottom: 14px;
}
.cc-rev-title { font-weight: 700; color: #1e2330; font-size: 0.88rem; margin-bottom: 8px; }
.cc-rev-body { font-size: 0.82rem; color: #475569; line-height: 1.55; }
.cc-rev-src { font-size: 0.71rem; color: #9ca3af; margin-top: 8px; }

/* ── Thread / conversation ───────────────────────────────────────────────── */
.cc-thread-q {
    background: #f1f5f9;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 0.88rem;
    font-weight: 600;
    color: #1e2330;
    margin: 18px 0 8px;
    border-left: 3px solid #3b5bdb;
}
.cc-thread-a {
    font-size: 0.88rem;
    color: #2d3347;
    line-height: 1.7;
    padding: 0 4px 16px;
    border-bottom: 1px solid #f1f5f9;
    margin-bottom: 4px;
}
.cc-thread-meta {
    font-size: 0.71rem;
    color: #9ca3af;
    margin-bottom: 4px;
}

/* ── Sidebar section label ───────────────────────────────────────────────── */
.cc-sidebar-label {
    font-size: 0.63rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #3d4456;
    padding: 4px 0 6px;
}

/* ── Empty state ─────────────────────────────────────────────────────────── */
.cc-empty {
    text-align: center;
    padding: 56px 20px;
    color: #9ba3b6;
}
.cc-empty-icon { font-size: 2.4rem; margin-bottom: 14px; }
.cc-empty-title { font-size: 0.98rem; font-weight: 600; color: #4d5469; margin-bottom: 8px; }
.cc-empty-sub { font-size: 0.83rem; line-height: 1.55; color: #9ba3b6; }

/* ── Corpus status pill in sidebar ──────────────────────────────────────── */
.cc-corpus-pill {
    display: flex;
    align-items: center;
    gap: 8px;
    background: #1e2a3d;
    border: 1px solid #2d3a55;
    border-radius: 8px;
    padding: 8px 12px;
    margin: 8px 0;
    font-size: 0.78rem;
    color: #8a93b0;
}
.cc-corpus-pill-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.cc-corpus-pill-dot.green { background: #22c55e; }
.cc-corpus-pill-dot.gray  { background: #4d5469; }

/* ── Sidebar material item ───────────────────────────────────────────────── */
.cc-mat-item {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 5px 6px;
    border-radius: 6px;
    margin-bottom: 2px;
}
.cc-mat-item-name { font-size: 0.79rem; font-weight: 600; color: #c2cae0; line-height: 1.3; }
.cc-mat-item-pages { font-size: 0.68rem; color: #4d5469; }

/* ── Responsive ──────────────────────────────────────────────────────────── */
@media (max-width: 900px) {
    .cc-table { font-size: 0.78rem; }
    .cc-table th, .cc-table td { padding: 8px 10px; }
    .cc-question-bubble { max-width: 100%; }
}
</style>
""", unsafe_allow_html=True)

# ── Session state bootstrap ────────────────────────────────────────────────────

# Each browser session gets a unique user_id — scopes all Supabase data
if "user_id" not in st.session_state:
    st.session_state["user_id"] = str(uuid.uuid4())

user_id = st.session_state["user_id"]

# Conversation memory backed by Supabase or Local SQLite
if "memory" not in st.session_state:
    from src.app.backend import get_memory
    st.session_state.memory = get_memory(user_id)

if "session_mgr" not in st.session_state:
    from src.conversation.session import SessionManager
    st.session_state.session_mgr = SessionManager(st.session_state.memory)

if "result"  not in st.session_state: st.session_state.result  = None
if "chunks"  not in st.session_state: st.session_state.chunks  = []
if "query"   not in st.session_state: st.session_state.query   = ""
if "history" not in st.session_state: st.session_state.history = []
if "bm25"    not in st.session_state: st.session_state.bm25    = None  # rebuilt lazily

# ── Render app ─────────────────────────────────────────────────────────────────
from src.app.sidebar  import render_sidebar
from src.app.page_ask import render_ask_page

render_sidebar()
render_ask_page()
