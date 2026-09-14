"""
Sidebar: dark navy branding, API key management, corpus status,
navigation (6 items), materials list, recent study threads.

Backend calls are all UNCHANGED — only presentation is redesigned.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── Cached helpers (scoped per user_id, cached 30 s) ──────────────────────────

@st.cache_data(ttl=30, show_spinner=False)
def _chunk_count(user_id: str) -> int:
    try:
        from src.storage.vector_store_supa import SupabaseVectorStore
        return SupabaseVectorStore(user_id).collection_size()
    except Exception:
        return 0


@st.cache_data(ttl=30, show_spinner=False)
def _registered_docs(user_id: str) -> list[dict]:
    try:
        from src.storage.registry_supa import SupabaseDocumentRegistry
        return SupabaseDocumentRegistry(user_id).list_documents()
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


# ── Timestamp formatter ────────────────────────────────────────────────────────

def _fmt_ts(ts_str: str) -> str:
    """Return a human-readable timestamp like 'Today, 2:36 AM'."""
    if not ts_str:
        return ""
    try:
        ts = ts_str.rstrip("Z")
        dt = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        diff = (now - dt).days
        time_str = dt.strftime("%I:%M %p").lstrip("0")
        if diff == 0:
            return f"Today, {time_str}"
        elif diff == 1:
            return f"Yesterday, {time_str}"
        else:
            return dt.strftime("%b %d, %I:%M %p").lstrip("0")
    except Exception:
        return ts_str[:10] if ts_str else ""


# ── Main sidebar renderer ──────────────────────────────────────────────────────

def render_sidebar() -> None:
    with st.sidebar:

        # ── Branding ─────────────────────────────────────────────────────────
        st.markdown(
            "<div style='padding:18px 16px 6px'>"
            "<div style='display:flex;align-items:center;gap:10px;margin-bottom:4px'>"
            "<span style='font-size:1.5rem'>📘</span>"
            "<span style='font-size:1.05rem;font-weight:700;color:#fff'>Course Companion</span>"
            "</div>"
            "<div style='font-size:.72rem;color:#4d5469;margin-bottom:8px'>"
            "Your materials. Clear answers. Higher confidence."
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )

        # ── Corpus status pill ────────────────────────────────────────────────
        user_id = st.session_state.get("user_id", "")
        n_chunks = _chunk_count(user_id)
        docs     = _registered_docs(user_id)
        n_docs   = len(docs)
        total_pages = sum(int(d.get("page_count", 0) or 0) for d in docs)

        if n_chunks > 0:
            st.markdown(
                f"<div class='cc-corpus-pill'>"
                f"<div class='cc-corpus-pill-dot green'></div>"
                f"<div><strong style='color:#e2e8f0'>{n_docs} documents</strong>"
                f" · {total_pages} pages · {n_chunks:,} chunks</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div class='cc-corpus-pill'>"
                "<div class='cc-corpus-pill-dot gray'></div>"
                "<div>No corpus indexed yet</div>"
                "</div>",
                unsafe_allow_html=True,
            )

        st.divider()

        # ── Navigation ────────────────────────────────────────────────────────
        st.markdown("<div style='padding:0 8px'>", unsafe_allow_html=True)

        if "page" not in st.session_state:
            st.session_state.page = "ask"

        nav_items = [
            ("💬", "Ask",          "ask"),
            ("📄", "Materials",    "materials"),
            ("💭", "Study Thread", "thread"),
            ("🔖", "Saved",        "saved"),
            ("📋", "Revision",     "revision"),
        ]

        for icon, label, key_p in nav_items:
            active = st.session_state.page == key_p
            if st.button(
                f"{icon}  {label}",
                key=f"nav_{key_p}",
                use_container_width=True,
                type="primary" if active else "secondary",
            ):
                st.session_state.page = key_p
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)
        st.divider()

        # ── Course Materials list ─────────────────────────────────────────────
        col_mat, col_up = st.columns([3, 1])
        with col_mat:
            st.markdown(
                "<div class='cc-sidebar-label'>Course Materials</div>",
                unsafe_allow_html=True,
            )
        with col_up:
            if st.button("＋", key="sidebar_upload_btn", help="Upload new materials"):
                st.session_state.page = "materials"
                st.rerun()

        fmt_icon = {
            "pdf-lecture": "📄", "pdf-slide": "📊",
            "markdown": "📝", "text": "📄",
            "handwritten": "✍️", "image-ocr": "✍️",
        }

        if docs:
            for doc in docs[:8]:
                icon = fmt_icon.get(doc.get("format", ""), "📄")
                pg   = doc.get("page_count", "?")
                nm   = doc["source_file"]
                nm_short = (nm[:26] + "…") if len(nm) > 28 else nm
                st.markdown(
                    f"<div class='cc-mat-item'>"
                    f"<span style='font-size:.9rem;flex-shrink:0'>{icon}</span>"
                    f"<div>"
                    f"<div class='cc-mat-item-name'>{nm_short}</div>"
                    f"<div class='cc-mat-item-pages'>{pg} pages</div>"
                    f"</div></div>",
                    unsafe_allow_html=True,
                )
            if len(docs) > 8:
                st.caption(f"  +{len(docs) - 8} more — see Materials page")
        else:
            st.caption("  No documents indexed yet.")

        st.divider()

        # ── Recent study threads ──────────────────────────────────────────────
        st.markdown(
            "<div class='cc-sidebar-label'>Recent Study Threads</div>",
            unsafe_allow_html=True,
        )

        try:
            sessions = st.session_state.memory.list_sessions()[:5]
            if sessions:
                for s in sessions:
                    topics = s.get("topics", [])
                    name   = s.get("name") or (topics[0] if topics else "Study session")
                    ts     = _fmt_ts(s.get("created_at", ""))
                    label  = f"💬  {name[:28]}"
                    if st.button(label, key=f"t_{s['session_id']}", use_container_width=True):
                        st.session_state.memory.switch_session(s["session_id"])
                        from src.conversation.session import SessionManager
                        st.session_state.session_mgr = SessionManager(st.session_state.memory)
                        st.session_state.page = "thread"
                        st.rerun()
                    if ts:
                        st.caption(f"   {ts}")
            else:
                st.caption("  No threads yet. Ask a question to start one.")
        except Exception:
            st.caption("  —")

        st.divider()

        # ── API key management ────────────────────────────────────────────────
        key = _active_key()
        if key:
            masked = key[:6] + "…" + key[-4:] if len(key) > 12 else "••••••••"
            st.markdown(
                f"🟢 <small><b>Gemini key</b> · <code>{masked}</code></small>",
                unsafe_allow_html=True,
            )
            with st.expander("🔑 Change API key"):
                new_k = st.text_input(
                    "New API key", type="password",
                    key="sidebar_change_key", placeholder="AIza…",
                )
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
                new_k = st.text_input(
                    "API key", type="password",
                    key="sidebar_new_key", placeholder="AIza…",
                )
                if st.button("Save key", key="save_key_btn", type="primary"):
                    if new_k.strip():
                        _apply_key(new_k)
                        st.success("Key saved!")
                        st.rerun()
                    else:
                        st.error("Please enter a key first.")

        # ── Footer ────────────────────────────────────────────────────────────
        st.markdown(
            "<div style='font-size:.72rem;color:#3d4456;padding:12px 0 4px'>"
            "🌙 Study smarter. Trust your sources."
            "</div>",
            unsafe_allow_html=True,
        )
