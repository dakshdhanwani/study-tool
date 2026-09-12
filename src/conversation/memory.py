"""
SQLite-backed conversation memory with session management and pinning.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.config import SQLITE_PATH, MAX_HISTORY_TURNS


class ConversationMemory:
    """Persistent conversation store backed by SQLite.

    Tables
    ------
    conversations : individual turns (user/assistant) with citation JSON.
    sessions      : session metadata (name, topics, docs).
    """

    def __init__(
        self,
        db_path: Path = SQLITE_PATH,
        session_id: Optional[str] = None,
    ) -> None:
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._create_schema()

        is_new = session_id is None
        self.session_id = session_id or str(uuid.uuid4())

        if is_new:
            self._create_session(self.session_id, name=None)
        else:
            exists = self._conn.execute(
                "SELECT 1 FROM sessions WHERE session_id=?", (self.session_id,)
            ).fetchone()
            if not exists:
                self._create_session(self.session_id, name=None)

    def _create_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id          TEXT PRIMARY KEY,
                session_id  TEXT NOT NULL,
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                citations   TEXT,
                timestamp   TEXT NOT NULL,
                is_pinned   INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_conv_session
                ON conversations (session_id, timestamp);

            CREATE TABLE IF NOT EXISTS sessions (
                session_id     TEXT PRIMARY KEY,
                name           TEXT,
                created_at     TEXT NOT NULL,
                topics         TEXT,
                docs_discussed TEXT
            );
        """)
        self._conn.commit()

    def _create_session(self, session_id: str, name: Optional[str]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT OR IGNORE INTO sessions (session_id, name, created_at, topics, docs_discussed)"
            " VALUES (?, ?, ?, ?, ?)",
            (session_id, name, now, "[]", "[]"),
        )
        self._conn.commit()

    # ── Turn management ──────────────────────────────────────────────────────

    def add_turn(self, role: str, content: str, citations: Optional[list] = None) -> str:
        turn_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO conversations (id, session_id, role, content, citations, timestamp, is_pinned)"
            " VALUES (?, ?, ?, ?, ?, ?, 0)",
            (turn_id, self.session_id, role, content, json.dumps(citations or []), now),
        )
        self._conn.commit()
        return turn_id

    def get_history(self, max_turns: int = MAX_HISTORY_TURNS) -> list[dict]:
        """Return last N turns as [{role, content}] in chronological order."""
        rows = self._conn.execute(
            "SELECT role, content FROM conversations"
            " WHERE session_id=? ORDER BY timestamp DESC LIMIT ?",
            (self.session_id, max_turns),
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    def get_full_history(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, role, content, citations, timestamp, is_pinned"
            " FROM conversations WHERE session_id=? ORDER BY timestamp ASC",
            (self.session_id,),
        ).fetchall()
        return [{
            "id": r["id"], "role": r["role"], "content": r["content"],
            "citations": json.loads(r["citations"] or "[]"),
            "timestamp": r["timestamp"], "is_pinned": bool(r["is_pinned"]),
        } for r in rows]

    def pin_turn(self, turn_id: str) -> None:
        self._conn.execute("UPDATE conversations SET is_pinned=1 WHERE id=?", (turn_id,))
        self._conn.commit()

    def unpin_turn(self, turn_id: str) -> None:
        self._conn.execute("UPDATE conversations SET is_pinned=0 WHERE id=?", (turn_id,))
        self._conn.commit()

    def get_pinned(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, role, content, citations, timestamp FROM conversations"
            " WHERE session_id=? AND is_pinned=1 ORDER BY timestamp ASC",
            (self.session_id,),
        ).fetchall()
        return [{
            "id": r["id"], "role": r["role"], "content": r["content"],
            "citations": json.loads(r["citations"] or "[]"),
            "timestamp": r["timestamp"], "is_pinned": True,
        } for r in rows]

    # ── Session management ──────────────────────────────────────────────────

    def list_sessions(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT session_id, name, created_at, topics, docs_discussed"
            " FROM sessions ORDER BY created_at DESC"
        ).fetchall()
        return [{
            "session_id": r["session_id"], "name": r["name"],
            "created_at": r["created_at"],
            "topics": json.loads(r["topics"] or "[]"),
            "docs_discussed": json.loads(r["docs_discussed"] or "[]"),
        } for r in rows]

    def switch_session(self, session_id: str) -> None:
        exists = self._conn.execute(
            "SELECT 1 FROM sessions WHERE session_id=?", (session_id,)
        ).fetchone()
        if not exists:
            self._create_session(session_id, name=None)
        self.session_id = session_id

    def new_session(self, name: Optional[str] = None) -> str:
        new_id = str(uuid.uuid4())
        self._create_session(new_id, name=name)
        self.session_id = new_id
        return new_id

    def update_session_topics(self, topics: list[str], docs: list[str]) -> None:
        self._conn.execute(
            "UPDATE sessions SET topics=?, docs_discussed=? WHERE session_id=?",
            (json.dumps(topics), json.dumps(docs), self.session_id),
        )
        self._conn.commit()

    def get_session_info(self) -> dict:
        row = self._conn.execute(
            "SELECT session_id, name, created_at, topics, docs_discussed"
            " FROM sessions WHERE session_id=?", (self.session_id,)
        ).fetchone()
        if not row:
            return {}
        return {
            "session_id": row["session_id"], "name": row["name"],
            "created_at": row["created_at"],
            "topics": json.loads(row["topics"] or "[]"),
            "docs_discussed": json.loads(row["docs_discussed"] or "[]"),
        }

    def rename_session(self, name: str) -> None:
        self._conn.execute(
            "UPDATE sessions SET name=? WHERE session_id=?", (name, self.session_id)
        )
        self._conn.commit()
