"""
Supabase PostgreSQL document registry — replaces SQLite DocumentRegistry.

Maps to the `documents` table. All operations scoped to user_id.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.config import TABLE_DOCUMENTS
from src.storage.supabase_client import get_supabase_client


class SupabaseDocumentRegistry:
    """PostgreSQL-backed registry tracking which files have been ingested per user."""

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id

    def _db(self):
        return get_supabase_client()

    def register(
        self,
        source_file: str,
        format: str,
        page_count: int,
        chunk_count: int,
        storage_path: str,
    ) -> None:
        """Insert or update a document record for this user."""
        now = datetime.now(timezone.utc).isoformat()
        (
            self._db()
            .table(TABLE_DOCUMENTS)
            .upsert(
                {
                    "user_id":      self.user_id,
                    "source_file":  source_file,
                    "format":       format,
                    "page_count":   page_count,
                    "chunk_count":  chunk_count,
                    "ingested_at":  now,
                    "storage_path": storage_path,
                },
                on_conflict="user_id,source_file",
            )
            .execute()
        )

    def is_ingested(self, source_file: str) -> bool:
        """Return True if source_file has already been ingested for this user."""
        resp = (
            self._db()
            .table(TABLE_DOCUMENTS)
            .select("source_file")
            .eq("user_id", self.user_id)
            .eq("source_file", source_file)
            .limit(1)
            .execute()
        )
        return bool(resp.data)

    def list_documents(self) -> list[dict]:
        """Return all documents ingested by this user, newest first."""
        resp = (
            self._db()
            .table(TABLE_DOCUMENTS)
            .select("source_file, format, page_count, chunk_count, ingested_at, storage_path")
            .eq("user_id", self.user_id)
            .order("ingested_at", desc=True)
            .execute()
        )
        return resp.data or []

    def get_document(self, source_file: str) -> Optional[dict]:
        """Return a single document record, or None if not found."""
        resp = (
            self._db()
            .table(TABLE_DOCUMENTS)
            .select("source_file, format, page_count, chunk_count, ingested_at, storage_path")
            .eq("user_id", self.user_id)
            .eq("source_file", source_file)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def delete_document(self, source_file: str) -> None:
        """Delete the registry record for a document."""
        (
            self._db()
            .table(TABLE_DOCUMENTS)
            .delete()
            .eq("user_id", self.user_id)
            .eq("source_file", source_file)
            .execute()
        )

