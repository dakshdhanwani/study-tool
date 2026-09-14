import os

def is_local_mode() -> bool:
    """If SUPABASE_URL is not provided, we run entirely on local disk (SQLite/Chroma)."""
    return not bool(os.environ.get("SUPABASE_URL"))

def get_memory(user_id: str):
    if is_local_mode():
        from src.conversation.memory import ConversationMemory
        # Local memory ignores user_id and scopes to session only
        return ConversationMemory(session_id=None)
    else:
        from src.storage.memory_supa import SupabaseConversationMemory
        return SupabaseConversationMemory(user_id)

def get_vector_store(user_id: str):
    if is_local_mode():
        from src.retrieval.vector_store import get_vector_store as get_local_vs
        return get_local_vs()
    else:
        from src.storage.vector_store_supa import SupabaseVectorStore
        return SupabaseVectorStore(user_id)

def get_registry(user_id: str):
    if is_local_mode():
        from src.ingestion.indexer import DocumentRegistry
        return DocumentRegistry()
    else:
        from src.storage.registry_supa import SupabaseDocumentRegistry
        return SupabaseDocumentRegistry(user_id)

def upload_file_backend(user_id: str, category: str, filename: str, data: bytes) -> str:
    if is_local_mode():
        from pathlib import Path
        corpus_dir = Path("corpus") / category
        corpus_dir.mkdir(parents=True, exist_ok=True)
        out_path = corpus_dir / filename
        out_path.write_bytes(data)
        return str(out_path)
    else:
        from src.storage.file_store import upload_file
        return upload_file(user_id=user_id, category=category, filename=filename, data=data)

def delete_file_backend(storage_path: str) -> None:
    if not storage_path: return
    if is_local_mode():
        from pathlib import Path
        try: Path(storage_path).unlink()
        except Exception: pass
    else:
        from src.storage.file_store import delete_file
        try: delete_file(storage_path)
        except Exception: pass
