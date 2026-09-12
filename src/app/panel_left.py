"""
Left panel — branding, navigation, materials list, recent study threads.
"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timezone
import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _nav_item(label: str, icon: str, page: str) -> None:
    active = st.session_state.get("page") == page
    cls = "cc-nav-item active" if active else "cc-nav-item"
    if st.button(f"{icon}  {label}", key=f"nav_{page}",
                 use_container_width=True,
                 type="primary" if active else "secondary"):
        st.session_state.page = page
        st.rerun()


def _corpus_files() -> list[dict]:
    """Return list of {name, pages, format, active} for materials sidebar."""
    corpus_dir = PROJECT_ROOT / "corpus"
    files = []
    for cat, glob_pat in [
        ("lectures", "*.pdf"), ("slides", "*.pdf"),
        ("notes", "*.md"), ("notes", "*.txt"),
        ("handwritten", "*.png"), ("handwritten", "*.jpg"),
    ]:
        d = corpus_dir / cat
        if d.exists():
            for f in sorted(d.glob(glob_pat)):
                files.append({"name": f.name, "cat": cat, "path": str(f)})

    # Try to enrich with registry data
    try:
        from src.ingestion.indexer import DocumentRegistry
        from src.config import SQLITE_PATH
        reg = DocumentRegistry(SQLITE_PATH)
        docs = {d["source_file"]: d for d in reg.list_documents()}
        for item in files:
            meta = docs.get(item["name"])
            if meta:
                item["pages"] = meta.get("page_count", "?")
                item["chunks"] = meta.get("chunk_count", 0)
    except Exception:
        pass

    return files


def _recent_threads() -> list[dict]:
    """Return recent conversation sessions."""
    try:
        mem = st.session_state.memory
        sessions = mem.list_sessions()
        result = []
        for s in sessions[:5]:
            created = s.get("created_at", "")
            # Format timestamp
            try:
                dt = datetime.fromisoformat(created.rstrip("Z"))
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                diff = now - dt
                if diff.days == 0:
                    ts = "Today, " + dt.strftime("%-I:%M %p") if hasattr(dt, 'strftime') else "Today"
                elif diff.days == 1:
                    ts = "Yesterday, " + dt.strftime("%-I:%M %p") if hasattr(dt, 'strftime') else "Yesterday"
                else:
                    ts = dt.strftime("%b %d, %I:%M %p") if hasattr(dt, 'strftime') else created[:10]
            except Exception:
                ts = created[:10] if created else ""

            topics = s.get("topics", [])
            title = s.get("name") or (topics[0] if topics else "Study session")
            result.append({"title": title[:34], "ts": ts, "sid": s["session_id"]})
        return result
    except Exception:
        return []


def render_left_panel() -> None:
    # ── Branding ──────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="cc-left">
      <div class="cc-brand">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px">
          <span style="font-size:1.5rem">📘</span>
          <p class="cc-brand-title">Course Companion</p>
        </div>
        <p class="cc-brand-sub">Your materials. Clear answers. Higher confidence.</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Navigation ────────────────────────────────────────────────────────────
    st.markdown('<div class="cc-nav" style="background:#1e2330;padding:8px;">', unsafe_allow_html=True)
    _nav_item("Home",     "🏠", "home")
    _nav_item("Ask",      "💬", "ask")
    _nav_item("Saved",    "🔖", "saved")
    _nav_item("Revision", "📋", "revision")
    _nav_item("Settings", "⚙️", "settings")
    st.markdown("</div>", unsafe_allow_html=True)

    st.divider()

    # ── Materials list ────────────────────────────────────────────────────────
    st.markdown('<div class="cc-section-label">MY COURSE MATERIALS</div>', unsafe_allow_html=True)

    files = _corpus_files()

    if not files:
        st.caption("No corpus ingested yet. Go to Settings → Ingest Corpus.")
    else:
        # Group by category
        cats = {}
        for f in files:
            cats.setdefault(f["cat"], []).append(f)

        cat_labels = {
            "lectures": "📂 Lectures", "slides": "📊 Slides",
            "notes": "📝 Notes", "handwritten": "✍️ Handwritten",
        }
        for cat, items in cats.items():
            with st.expander(cat_labels.get(cat, cat), expanded=(cat == "lectures")):
                for item in items:
                    pages = item.get("pages", "")
                    pages_str = f"{pages} pages" if pages else ""
                    is_active = st.session_state.get("active_file") == item["name"]
                    label = f"{'● ' if is_active else '  '}{item['name']}"
                    if st.button(label, key=f"file_{item['name']}", use_container_width=True):
                        st.session_state.active_file = item["name"]
                    if pages_str:
                        st.caption(f"  {pages_str}")

    st.divider()

    # ── Ingestion shortcut ────────────────────────────────────────────────────
    try:
        from src.retrieval.vector_store import get_vector_store
        vs = get_vector_store()
        n = vs.collection_size()
        if n == 0:
            st.warning("Not yet ingested.")
            if st.button("🚀 Ingest corpus", use_container_width=True, type="primary"):
                with st.spinner("Ingesting…"):
                    from src.ingestion.indexer import ingest_corpus
                    r = ingest_corpus()
                    st.success(f"{r['total_documents']} docs, {r['total_chunks']} chunks")
                    st.rerun()
        else:
            st.caption(f"🟢 {n:,} chunks indexed")
    except Exception:
        st.caption("Vector store loading…")

    st.divider()

    # ── Recent threads ────────────────────────────────────────────────────────
    st.markdown('<div class="cc-section-label">RECENT STUDY THREADS</div>', unsafe_allow_html=True)

    threads = _recent_threads()
    if not threads:
        st.caption("No threads yet.")
    else:
        for t in threads:
            if st.button(f"💬  {t['title']}", key=f"thread_{t['sid']}", use_container_width=True):
                mem = st.session_state.memory
                mem.switch_session(t["sid"])
                from src.conversation.session import SessionManager
                st.session_state.session_mgr = SessionManager(mem)
                st.session_state.page = "ask"
                st.rerun()
            st.caption(f"   {t['ts']}")

    # ── Footer ────────────────────────────────────────────────────────────────
    st.markdown("""<div class="cc-footer" style="background:#1e2330;color:#4d5469;
        font-size:.72rem;padding:10px 16px;margin-top:auto">
        🌙 Good luck — you've got this.
    </div>""", unsafe_allow_html=True)
