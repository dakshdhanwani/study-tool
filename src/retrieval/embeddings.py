"""
Embedding model wrapper using sentence-transformers.
"""
from __future__ import annotations

from typing import Optional
import numpy as np

EMBEDDING_MODEL = "all-MiniLM-L6-v2"


class EmbeddingModel:
    """Lazy-loading SentenceTransformer wrapper."""

    def __init__(self, model_name: str = EMBEDDING_MODEL) -> None:
        self._model_name = model_name
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
        return self._model

    def embed(self, texts: list[str]) -> np.ndarray:
        """Encode a list of texts, returning an (n, dim) float32 array."""
        if not texts:
            return np.empty((0,), dtype=np.float32)
        return self.model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=True,
        )

    def embed_one(self, text: str) -> np.ndarray:
        """Encode a single string into a 1-D embedding vector."""
        return self.embed([text])[0]

    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Cosine similarity between two L2-normalised vectors."""
        a = np.asarray(a, dtype=np.float64).ravel()
        b = np.asarray(b, dtype=np.float64).ravel()
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(a, b) / (na * nb))


import streamlit as st


@st.cache_resource(show_spinner=False)
def get_embedder() -> EmbeddingModel:
    """Return the embedding model — cached for the Streamlit server lifetime.

    Uses @st.cache_resource so the 90 MB sentence-transformer model is loaded
    exactly ONCE when the server starts, and reused for all subsequent calls.
    """
    return EmbeddingModel()
