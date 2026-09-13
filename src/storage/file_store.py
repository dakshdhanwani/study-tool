"""
Supabase Storage file operations — upload, download, delete, list.

All paths are scoped per user:  {user_id}/{category}/{filename}
Bucket name is read from config (SUPABASE_BUCKET, default: "documents").
"""
from __future__ import annotations

from pathlib import Path
from src.config import SUPABASE_BUCKET
from src.storage.supabase_client import get_supabase_client


def _bucket():
    return get_supabase_client().storage.from_(SUPABASE_BUCKET)


def upload_file(user_id: str, category: str, filename: str, data: bytes) -> str:
    """Upload file bytes to Supabase Storage.

    Parameters
    ----------
    user_id:   The visitor's UUID.
    category:  'lectures' | 'slides' | 'notes' | 'handwritten'
    filename:  Original filename, e.g. 'my_notes.pdf'
    data:      Raw file bytes.

    Returns
    -------
    str
        The storage path, e.g. '{user_id}/lectures/my_notes.pdf'
    """
    path = f"{user_id}/{category}/{filename}"
    _bucket().upload(
        path=path,
        file=data,
        file_options={"upsert": "true"},
    )
    return path


def download_file(storage_path: str) -> bytes:
    """Download a file from Supabase Storage and return raw bytes."""
    return _bucket().download(storage_path)


def delete_file(storage_path: str) -> None:
    """Delete a file from Supabase Storage."""
    try:
        _bucket().remove([storage_path])
    except Exception:
        pass   # file may already be gone


def list_user_files(user_id: str) -> list[dict]:
    """List all files belonging to a user.

    Returns list of dicts with keys: name, storage_path, size, created_at.
    """
    results = []
    for category in ("lectures", "slides", "notes", "handwritten"):
        prefix = f"{user_id}/{category}"
        try:
            items = _bucket().list(prefix)
            for item in items or []:
                results.append({
                    "name":         item.get("name", ""),
                    "category":     category,
                    "storage_path": f"{prefix}/{item.get('name', '')}",
                    "size":         item.get("metadata", {}).get("size", 0),
                    "created_at":   item.get("created_at", ""),
                })
        except Exception:
            pass
    return results


def get_signed_url(storage_path: str, expires_in: int = 3600) -> str:
    """Generate a temporary signed URL for viewing a file (e.g. page images)."""
    resp = _bucket().create_signed_url(storage_path, expires_in)
    return resp.get("signedURL", "")

