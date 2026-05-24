"""In-process embeddings via sentence-transformers (no llama-server on :8082)."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

_DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
_MODEL_CACHE: dict[str, Any] = {}


class LocalEmbeddingProvider:
    """Lightweight CPU/MPS embeddings (~120 MB RAM vs ~1 GB for a second llama-server)."""

    DIMENSIONS = 384  # all-MiniLM-L6-v2

    def __init__(self, model_name: str = _DEFAULT_MODEL) -> None:
        self._model_name = model_name

    def _load_model(self) -> Any:
        if self._model_name in _MODEL_CACHE:
            return _MODEL_CACHE[self._model_name]
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise RuntimeError(
                "Local embeddings require sentence-transformers. "
                'Install with: pip install -e ".[embeddings]" '
                "or set CEREBRO_EMBEDDINGS_BACKEND=llamacpp"
            ) from e

        device = "cpu"
        try:
            import torch

            if torch.backends.mps.is_available():
                device = "mps"
        except Exception:
            pass

        logger.info("Loading local embedding model {} on {}", self._model_name, device)
        model = SentenceTransformer(self._model_name, device=device)
        _MODEL_CACHE[self._model_name] = model
        return model

    def _encode_sync(self, text: str) -> list[float]:
        model = self._load_model()
        vec = model.encode(text, normalize_embeddings=True, convert_to_numpy=True)
        return [float(x) for x in vec.tolist()]

    async def embed(self, text: str) -> list[float]:
        return await asyncio.to_thread(self._encode_sync, text)

    def dimensions(self) -> int:
        return self.DIMENSIONS

    @property
    def name(self) -> str:
        return "local-embed"
