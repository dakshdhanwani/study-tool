"""
Sidebar: branding, API key management, corpus status, materials list, recent threads.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── Cached helpers (run once every 30 s, not on every rerender) ───────────────

@st.cache_data(ttl=30, show_spinner=False)
def _chunk_count() -> int:
    try:
        from src.retrieval.vector_store import get_vector_store
        return get_vector_store().collection_size()
    except Exception:
        return 0


@st.cache_data(ttl=30, show_spinner=False)
def _registered_docs() -> list[dict]:
    try:
        from src.ingestion.indexer import DocumentRegistry
        from src.config import SQLITE_PATH
        return DocumentRegistry(SQLITE_PATH).list_documents()
    except Exception:
        return []


# ── API key helpers ────────────────────────────────────────────────────────────

def _active_key() -> str:
    """Return the currently active API key (session → env)."""
    return (
        st.session_state.get("gemini_api_key", "")
        or os.environ.get("GEMINI_API_KEY", "")
    )


def _save_key_to_secrets(key: str) -> None:
    """Persist key to .streamlit/secrets.toml so it survives app restarts."""
    secrets_path = PROJECT_ROOT / ".streamlit" / "secrets.toml"
    secrets_path.parent.mkdir(parents=True, exist_ok=True)
    content = f'GEMINI_API_KEY = "{key}"\n'
    secrets_path.write_text(content, encoding="utf-8")


def _apply_key(key: str) -> None:
    """Store key in session state, OS environment, and local secrets file."""
    key = key.strip()
    st.session_state["gemini_api_key"] = key
    os.environ["GEMINI_API_KEY"] = key
    _save_key_to_secrets(key)


# ── Main sidebar renderer ──────────────────────────────────────────────────────

def render_sidebar() -> None:
    with st.sidebar:
        # ── Branding ─────────────────────────────────────────────────────────
        st.markdown(
            "<div style='display:flex;align-items:center;gap:10px;margin-bottom:2px'>"
            "<span style='font-size:1.6rem'>📘</span>"
            "<span style='font-size:1.05rem;font-weight:700;color:#fff'>Course Companion</span>"
            "</div>"
            "<div style='font-size:.72rem;color:#5d6580;margin-bottom:12px'>"
            "Your materials. Clear answers. Higher confidence.</div>",
            unsafe_allow_html=True,
        )

        # ── API key management ────────────────────────────────────────────────
        key = _active_key()
        if key:
            masked = key[:6] + "…" + key[-4:] if len(key) > 12 else "••••••••"
            st.markdown(
                f"🟢 <small><b>Gemini key</b> · <code>{masked}</code></small>",
                unsafe_allow_html=True,
            )
            with st.expander("🔑 Change API key"):
                new_k = st.text_input("New API key", type="password", key="sidebar_change_key",
                                      placeholder="AIza…")
                if st.button("Update key", key="update_key_btn"):
                    if new_k.strip():
                        _apply_key(new_k)
                        st.success("Key updated and saved!")
                        st.rerun()
                    else:
                        st.error("Please enter a key.")
        else:
            st.warning("⚠️ No API key set")
            with st.expander("🔑 Enter Gemini API key", expanded=True):
                st.markdown(
                    "<small>Get a free key at "
                    "[aistudio.google.com](https://aistudio.google.com/app/apikey)</small>",
                    unsafe_allow_html=True,
                )
                new_k = st.text_input("API key", type="password", key="sidebar_new_key",
                                      placeholder="AIza…")
                if st.button("Save key", key="save_key_btn", type="primary"):
                    if new_k.strip():
                        _apply_key(new_k)
                        st.success("Key saved!")
                        st.rerun()
                    else:
                        st.error("Please enter a key first.")

        st.divider()

        # ── Corpus status ─────────────────────────────────────────────────────
        n = _chunk_count()
        if n > 0:
            st.markdown(
                f"🟢 <small><b>{n:,} chunks</b> indexed and ready</small>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "⚪ <small>No corpus indexed — go to <b>My Materials</b> to upload</small>",
                unsafe_allow_html=True,
            )

        st.divider()

        # ── Navigation ────────────────────────────────────────────────────────
        pages = {
            "💬 Ask":          "ask",
            "📁 My Materials": "materials",
            "🔖 Saved":        "saved",
            "📋 Revision":     "revision",
        }
        if "page" not in st.session_state:
            st.session_state.page = "ask"

        for label, key_p in pages.items():
            active = st.session_state.page == key_p
            if st.button(
                label,
                key=f"nav_{key_p}",
                use_container_width=True,
                type="primary" if active else "secondary",
            ):
                st.session_state.page = key_p
                st.rerun()

        st.divider()

        # ── Materials list ────────────────────────────────────────────────────
        docs = _registered_docs()
        if docs:
            st.markdown(
                "<div style='font-size:.68rem;font-weight:600;letter-spacing:.08em;"
                "text-transform:uppercase;color:#5d6580;margin-bottom:6px'>"
                "INDEXED MATERIALS</div>",
                unsafe_allow_html=True,
            )
            fmt_icon = {
                "pdf-lecture": "📄", "pdf-slide": "📊",
                "markdown": "📝", "text": "📄",
                "handwritten": "✍️", "image-ocr": "✍️",
            }
            for doc in docs[:10]:
                icon = fmt_icon.get(doc.get("format", ""), "📄")
                pg   = doc.get("page_count", "?")
                st.markdown(
                    f"<div style='font-size:.8rem;padding:3px 0;color:#c2c8d8'>"
                    f"{icon} <b>{doc['source_file']}</b>"
                    f"<span style='color:#5d6580;margin-left:6px'>{pg} pages</span></div>",
                    unsafe_allow_html=True,
                )
            if len(docs) > 10:
                st.caption(f"  +{len(docs)-10} more")

        st.divider()

        # ── Recent threads ────────────────────────────────────────────────────
        try:
            sessions = st.session_state.memory.list_sessions()[:4]
            if sessions:
                st.markdown(
                    "<div style='font-size:.68rem;font-weight:600;letter-spacing:.08em;"
                    "text-transform:uppercase;color:#5d6580;margin-bottom:4px'>"
                    "RECENT THREADS</div>",
                    unsafe_allow_html=True,
                )
                for s in sessions:
                    topics = s.get("topics", [])
                    name   = s.get("name") or (topics[0] if topics else "Session")
                    ts     = s.get("created_at", "")[:10]
                    if st.button(f"💬 {name[:28]}", key=f"t_{s['session_id']}", use_container_width=True):
                        st.session_state.memory.switch_session(s["session_id"])
                        from src.conversation.session import SessionManager
                        st.session_state.session_mgr = SessionManager(st.session_state.memory)
                        st.rerun()
                    st.caption(f"   {ts}")
        except Exception:
            pass

        # ── Footer ────────────────────────────────────────────────────────────
        st.markdown(
            "<div style='font-size:.72rem;color:#3d4456;padding-top:12px'>"
            "🌙 Good luck — you've got this.</div>",
            unsafe_allow_html=True,
        )

