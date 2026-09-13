"""
Supabase PostgreSQL conversation memory — replaces SQLite ConversationMemory.

Same public API as src/conversation/memory.py so the rest of the app is unaffected.
All data scoped to (user_id, session_id).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from src.config import TABLE_CONVERSATIONS, TABLE_SESSIONS, MAX_HISTORY_TURNS
from src.storage.supabase_client import get_supabase_client


class SupabaseConversationMemory:
    """Persistent conversation store backed by Supabase PostgreSQL."""

    def __init__(self, user_id: str, session_id: Optional[str] = None) -> None:
        self.user_id = user_id
        is_new = session_id is None
        self.session_id = session_id or str(uuid.uuid4())
        if is_new:
            self._create_session(self.session_id, name=None)
        else:
            self._ensure_session_exists()

    def _db(self):
        return get_supabase_client()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── Session bootstrap ─────────────────────────────────────────────────────

    def _ensure_session_exists(self) -> None:
        resp = (
            self._db()
            .table(TABLE_SESSIONS)
            .select("session_id")
            .eq("session_id", self.session_id)
            .eq("user_id", self.user_id)
            .limit(1)
            .execute()
        )
        if not resp.data:
            self._create_session(self.session_id, name=None)

    def _create_session(self, session_id: str, name: Optional[str]) -> None:
        (
            self._db()
            .table(TABLE_SESSIONS)
            .upsert(
                {
                    "session_id":     session_id,
                    "user_id":        self.user_id,
                    "name":           name,
                    "created_at":     self._now(),
                    "topics":         [],
                    "docs_discussed": [],
                },
                on_conflict="session_id",
            )
            .execute()
        )

    # ── Turn management ───────────────────────────────────────────────────────

    def add_turn(self, role: str, content: str, citations: Optional[list] = None) -> str:
        turn_id = str(uuid.uuid4())
        (
            self._db()
            .table(TABLE_CONVERSATIONS)
            .insert({
                "id":         turn_id,
                "user_id":    self.user_id,
                "session_id": self.session_id,
                "role":       role,
                "content":    content,
                "citations":  citations or [],
                "timestamp":  self._now(),
                "is_pinned":  False,
            })
            .execute()
        )
        return turn_id

    def get_history(self, max_turns: int = MAX_HISTORY_TURNS) -> list[dict]:
        """Return the last N turns as [{role, content}] in chronological order."""
        resp = (
            self._db()
            .table(TABLE_CONVERSATIONS)
            .select("role, content, timestamp")
            .eq("user_id", self.user_id)
            .eq("session_id", self.session_id)
            .order("timestamp", desc=True)
            .limit(max_turns)
            .execute()
        )
        rows = resp.data or []
        # Reverse so oldest first
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    def get_full_history(self) -> list[dict]:
        resp = (
            self._db()
            .table(TABLE_CONVERSATIONS)
            .select("id, role, content, citations, timestamp, is_pinned")
            .eq("user_id", self.user_id)
            .eq("session_id", self.session_id)
            .order("timestamp")
            .execute()
        )
        return [
            {
                "id":        r["id"],
                "role":      r["role"],
                "content":   r["content"],
                "citations": r.get("citations") or [],
                "timestamp": r["timestamp"],
                "is_pinned": bool(r.get("is_pinned", False)),
            }
            for r in (resp.data or [])
        ]

    def pin_turn(self, turn_id: str) -> None:
        (
            self._db()
            .table(TABLE_CONVERSATIONS)
            .update({"is_pinned": True})
            .eq("id", turn_id)
            .eq("user_id", self.user_id)
            .execute()
        )

    def unpin_turn(self, turn_id: str) -> None:
        (
            self._db()
            .table(TABLE_CONVERSATIONS)
            .update({"is_pinned": False})
            .eq("id", turn_id)
            .eq("user_id", self.user_id)
            .execute()
        )

    def get_pinned(self) -> list[dict]:
        resp = (
            self._db()
            .table(TABLE_CONVERSATIONS)
            .select("id, role, content, citations, timestamp")
            .eq("user_id", self.user_id)
            .eq("session_id", self.session_id)
            .eq("is_pinned", True)
            .order("timestamp")
            .execute()
        )
        return [
            {
                "id":        r["id"],
                "role":      r["role"],
                "content":   r["content"],
                "citations": r.get("citations") or [],
                "timestamp": r["timestamp"],
                "is_pinned": True,
            }
            for r in (resp.data or [])
        ]

    # ── Session management ────────────────────────────────────────────────────

    def list_sessions(self) -> list[dict]:
        resp = (
            self._db()
            .table(TABLE_SESSIONS)
            .select("session_id, name, created_at, topics, docs_discussed")
            .eq("user_id", self.user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return [
            {
                "session_id":     r["session_id"],
                "name":           r.get("name"),
                "created_at":     r["created_at"],
                "topics":         r.get("topics") or [],
                "docs_discussed": r.get("docs_discussed") or [],
            }
            for r in (resp.data or [])
        ]

    def switch_session(self, session_id: str) -> None:
        self.session_id = session_id
        self._ensure_session_exists()

    def new_session(self, name: Optional[str] = None) -> str:
        new_id = str(uuid.uuid4())
        self._create_session(new_id, name=name)
        self.session_id = new_id
        return new_id

    def update_session_topics(self, topics: list[str], docs: list[str]) -> None:
        (
            self._db()
            .table(TABLE_SESSIONS)
            .update({"topics": topics, "docs_discussed": docs})
            .eq("session_id", self.session_id)
            .eq("user_id", self.user_id)
            .execute()
        )

    def get_session_info(self) -> dict:
        resp = (
            self._db()
            .table(TABLE_SESSIONS)
            .select("session_id, name, created_at, topics, docs_discussed")
            .eq("session_id", self.session_id)
            .eq("user_id", self.user_id)
            .limit(1)
            .execute()
        )
        if not resp.data:
            return {}
        r = resp.data[0]
        return {
            "session_id":     r["session_id"],
            "name":           r.get("name"),
            "created_at":     r["created_at"],
            "topics":         r.get("topics") or [],
            "docs_discussed": r.get("docs_discussed") or [],
        }

    def rename_session(self, name: str) -> None:
        (
            self._db()
            .table(TABLE_SESSIONS)
            .update({"name": name})
            .eq("session_id", self.session_id)
            .eq("user_id", self.user_id)
            .execute()
        )

