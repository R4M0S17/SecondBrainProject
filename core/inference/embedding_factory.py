"""Select embedding backend: in-process (local) or llama-server HTTP (llamacpp)."""

from __future__ import annotations

import os

import psutil

from core.inference.providers.llamacpp_embedding_provider import LlamaCppEmbeddingProvider
from core.inference.providers.local_embedding_provider import LocalEmbeddingProvider
from core.inference.registry import EmbeddingProvider

_EMBED_RAM_LOCAL_DEFAULT_GB = 10.0


def default_embeddings_backend() -> str:
    """Use local embeddings on ≤10 GB machines unless overridden."""
    explicit = os.getenv("CEREBRO_EMBEDDINGS_BACKEND", "").strip().lower()
    if explicit:
        return explicit
    total_gb = psutil.virtual_memory().total / (1024**3)
    if total_gb <= _EMBED_RAM_LOCAL_DEFAULT_GB:
        return "local"
    return "llamacpp"


def build_embedding_provider(
    *,
    embed_url: str = "http://127.0.0.1:8082",
    embed_model: str = "jina-embeddings",
) -> EmbeddingProvider:
    backend = default_embeddings_backend()
    if backend == "local":
        model_name = os.getenv(
            "CEREBRO_LOCAL_EMBED_MODEL",
            "sentence-transformers/all-MiniLM-L6-v2",
        )
        return LocalEmbeddingProvider(model_name=model_name)
    if backend == "llamacpp":
        return LlamaCppEmbeddingProvider(base_url=embed_url, model=embed_model)
    raise ValueError(
        f"Unknown CEREBRO_EMBEDDINGS_BACKEND={backend!r} " '(expected "local" or "llamacpp")'
    )
