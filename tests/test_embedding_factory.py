from __future__ import annotations

import pytest

from core.inference.embedding_factory import build_embedding_provider, default_embeddings_backend
from core.inference.providers.llamacpp_embedding_provider import LlamaCppEmbeddingProvider
from core.inference.providers.local_embedding_provider import LocalEmbeddingProvider


def test_default_embeddings_backend_respects_env(monkeypatch):
    monkeypatch.setenv("CEREBRO_EMBEDDINGS_BACKEND", "llamacpp")
    assert default_embeddings_backend() == "llamacpp"


def test_build_embedding_provider_llamacpp(monkeypatch):
    monkeypatch.setenv("CEREBRO_EMBEDDINGS_BACKEND", "llamacpp")
    provider = build_embedding_provider(embed_url="http://127.0.0.1:8082")
    assert isinstance(provider, LlamaCppEmbeddingProvider)
    assert provider.dimensions() == 1024


def test_build_embedding_provider_local(monkeypatch):
    monkeypatch.setenv("CEREBRO_EMBEDDINGS_BACKEND", "local")
    provider = build_embedding_provider()
    assert isinstance(provider, LocalEmbeddingProvider)
    assert provider.dimensions() == 384


def test_build_embedding_provider_unknown_raises(monkeypatch):
    monkeypatch.setenv("CEREBRO_EMBEDDINGS_BACKEND", "invalid")
    with pytest.raises(ValueError, match="Unknown CEREBRO_EMBEDDINGS_BACKEND"):
        build_embedding_provider()
