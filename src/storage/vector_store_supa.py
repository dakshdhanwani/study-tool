"""
Supabase pgvector-backed vector store — replaces ChromaDB.

Uses the `chunks` table with a `vector(384)` column and ivfflat index.
All operations are scoped to a `user_id` so users are fully isolated.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from src.config import RETRIEVAL_TOP_K, TABLE_CHUNKS
from src.ingestion.chunker import Chunk
from src.retrieval.embeddings import get_embedder
from src.storage.supabase_client import get_supabase_client

_BATCH_SIZE = 50   # Supabase insert batch size


class SupabaseVectorStore:
    """pgvector-backed vector store scoped to a single user."""

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id

    def _db(self):
        return get_supabase_client()

    # ── Write ─────────────────────────────────────────────────────────────────

    def add_chunks(self, chunks: list[Chunk]) -> None:
        """Embed chunks and upsert into the `chunks` table in batches."""
        embedder = get_embedder()
        for start in range(0, len(chunks), _BATCH_SIZE):
            batch = chunks[start: start + _BATCH_SIZE]
            texts = [c.text for c in batch]
            embeddings: np.ndarray = embedder.embed(texts)

            rows = []
            for c, emb in zip(batch, embeddings):
                rows.append({
                    "user_id":        self.user_id,
                    "source_file":    str(c.source_file),
                    "chunk_id":       str(c.chunk_id),
                    "page_number":    int(c.page_number),
                    "chunk_index":    int(c.chunk_index),
                    "text":           c.text,
                    "format":         str(c.format),
                    "ocr_confidence": float(c.ocr_confidence) if c.ocr_confidence is not None else 1.0,
                    "storage_path":   str(c.page_image_path) if c.page_image_path else "",
                    "section_title":  c.section_title or "",
                    # pgvector expects a plain Python list
                    "embedding":      emb.tolist(),
                })

            (
                self._db()
                .table(TABLE_CHUNKS)
                .upsert(rows, on_conflict="chunk_id")
                .execute()
            )

    def delete_chunks_for_document(self, source_file: str) -> None:
        """Delete all chunks belonging to source_file for this user."""
        (
            self._db()
            .table(TABLE_CHUNKS)
            .delete()
            .eq("user_id", self.user_id)
            .eq("source_file", source_file)
            .execute()
        )

    # ── Read ──────────────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = RETRIEVAL_TOP_K) -> list[dict[str, Any]]:
        """Semantic similarity search using pgvector cosine distance.

        Uses Supabase RPC function `match_chunks` (defined in SQL below).

        SQL function to create once in Supabase SQL Editor:

            create or replace function match_chunks(
                query_embedding vector(384),
                match_user_id   text,
                match_count     int
            )
            returns table (
                chunk_id       text,
                source_file    text,
                page_number    int,
                chunk_index    int,
                text           text,
                format         text,
                ocr_confidence float,
                storage_path   text,
                section_title  text,
                similarity     float
            )
            language sql stable
            as $$
                select
                    chunk_id, source_file, page_number, chunk_index,
                    text, format, ocr_confidence, storage_path, section_title,
                    1 - (embedding <=> query_embedding) as similarity
                from chunks
                where user_id = match_user_id
                order by embedding <=> query_embedding
                limit match_count;
            $$;
        """
        embedder = get_embedder()
        query_vec = embedder.embed_one(query).tolist()

        resp = (
            self._db()
            .rpc("match_chunks", {
                "query_embedding": query_vec,
                "match_user_id":   self.user_id,
                "match_count":     top_k,
            })
            .execute()
        )

        results = []
        for row in (resp.data or []):
            results.append({
                "chunk_id": row["chunk_id"],
                "text":     row["text"],
                "score":    float(row.get("similarity", 0.0)),
                "metadata": {
                    "source_file":    row.get("source_file", ""),
                    "page_number":    row.get("page_number", 1),
                    "format":         row.get("format", ""),
                    "ocr_confidence": row.get("ocr_confidence", 1.0),
                    "page_image_path": row.get("storage_path", ""),
                    "section_title":  row.get("section_title", ""),
                },
            })
        return results

    def get_chunk_by_id(self, chunk_id: str) -> dict[str, Any] | None:
        """Fetch a single chunk by its chunk_id."""
        resp = (
            self._db()
            .table(TABLE_CHUNKS)
            .select("chunk_id, text, source_file, page_number, format, ocr_confidence, storage_path, section_title")
            .eq("chunk_id", chunk_id)
            .eq("user_id", self.user_id)
            .limit(1)
            .execute()
        )
        if not resp.data:
            return None
        row = resp.data[0]
        return {
            "chunk_id": row["chunk_id"],
            "text":     row["text"],
            "metadata": {
                "source_file":    row.get("source_file", ""),
                "page_number":    row.get("page_number", 1),
                "format":         row.get("format", ""),
                "ocr_confidence": row.get("ocr_confidence", 1.0),
                "page_image_path": row.get("storage_path", ""),
                "section_title":  row.get("section_title", ""),
            },
        }

    def get_all_chunks(self) -> list[dict[str, Any]]:
        """Return all chunks for this user — used to rebuild BM25 in memory."""
        resp = (
            self._db()
            .table(TABLE_CHUNKS)
            .select("chunk_id, text")
            .eq("user_id", self.user_id)
            .execute()
        )
        return [{"chunk_id": r["chunk_id"], "text": r["text"]} for r in (resp.data or [])]

    def collection_size(self) -> int:
        """Return total number of chunks indexed for this user."""
        resp = (
            self._db()
            .table(TABLE_CHUNKS)
            .select("chunk_id", count="exact")
            .eq("user_id", self.user_id)
            .execute()
        )
        return resp.count or 0

