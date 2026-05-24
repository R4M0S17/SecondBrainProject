from __future__ import annotations

import pytest

from core.inference.providers import local_embedding_provider as lep


@pytest.mark.asyncio
async def test_local_embed_returns_384_dims(mocker):
    fake_vec = [0.1] * lep.LocalEmbeddingProvider.DIMENSIONS

    class FakeModel:
        def encode(self, text, *, normalize_embeddings, convert_to_numpy):
            assert text == "hello"
            assert normalize_embeddings is True
            assert convert_to_numpy is True

            class Arr:
                def tolist(self):
                    return fake_vec

            return Arr()

    mocker.patch.dict(lep._MODEL_CACHE, {}, clear=True)
    mocker.patch.object(
        lep.LocalEmbeddingProvider,
        "_load_model",
        return_value=FakeModel(),
    )

    provider = lep.LocalEmbeddingProvider()
    result = await provider.embed("hello")
    assert result == fake_vec
    assert len(result) == 384
    assert provider.name == "local-embed"


def test_local_embed_import_error_message(mocker):
    import builtins

    mocker.patch.dict(lep._MODEL_CACHE, {}, clear=True)
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "sentence_transformers":
            raise ImportError("no st")
        return real_import(name, globals, locals, fromlist, level)

    mocker.patch("builtins.__import__", side_effect=fake_import)
    provider = lep.LocalEmbeddingProvider()
    with pytest.raises(RuntimeError, match="sentence-transformers"):
        provider._encode_sync("x")
