"""Tests for SemanticCompressor — both Path A (neural/llama.cpp embeddings)
and Path B (TF-IDF), with mocked llama.cpp embedding endpoint."""

import hashlib
import re
import time
import tracemalloc
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from core.memory.vector_store import SearchResult
from core.utils.compressor import SemanticCompressor, SentenceUnit

NOW = time.strftime("%Y%m%dT%H%M%S")
RESULTS_FILE = f"test_semantic_compressor_results_{NOW}.txt"


def _chunk(source: str, idx: int, content: str) -> SearchResult:
    return SearchResult(
        id=hashlib.sha256(content.encode()).hexdigest(),
        content=content,
        source_path=source,
        chunk_index=idx,
        score=0.9,
        metadata={},
    )


def _estimated_tokens(text: str) -> int:
    return max(1, len(text) // 4)


# ── test data ────────────────────────────────────────────────────────────

MULTI_CHUNK_CONTENTS = [
    (
        "Gradient descent is an iterative optimization algorithm used in machine learning. "
        "It minimizes the loss function by moving in the direction of steepest descent. "
        "The learning rate controls step size during each iteration. "
        "Too large a learning rate can cause divergence from the minimum. "
        "Too small a learning rate results in very slow convergence. "
        "Stochastic gradient descent uses a single training example per update. "
        "Mini-batch gradient descent balances efficiency and stability. "
        "Adam is a popular adaptive optimization algorithm in deep learning."
    ),
    (
        "La regla de la cadena permite calcular la derivada de funciones compuestas. "
        "Si f(g(x)) es una función compuesta, su derivada es f'(g(x)) * g'(x). "
        "Este teorema es fundamental en cálculo diferencial y sus aplicaciones. "
        "Permite descomponer funciones complejas en partes más simples. "
        "Por ejemplo, la derivada de sin(x^2) es cos(x^2) * 2x. "
        "Es esencial en física, ingeniería, economía y optimización."
    ),
    (
        "Photosynthesis converts light energy into chemical energy in plants. "
        "This process occurs in chloroplasts containing chlorophyll pigment. "
        "Plants take in carbon dioxide and water during photosynthesis. "
        "The products are glucose and oxygen through this process. "
        "The chemical equation is 6CO2 + 6H2O + light -> C6H12O6 + 6O2. "
        "It has two stages: light-dependent reactions and the Calvin cycle."
    ),
    (
        "Paris is the capital of France with approximately 2.1 million residents. "
        "The metropolitan area of Paris contains over 12 million people. "
        "It is located in the north-central part of the country. "
        "Paris is divided into 20 arrondissements with distinct character. "
        "It is a global center for art, fashion, cuisine and culture. "
        "The Eiffel Tower and Louvre Museum are famous landmarks."
    ),
]

TEST_QUERIES = [
    "What is gradient descent in machine learning?",
    "Derivada de una función compuesta regla de la cadena",
    "Fotosíntesis proceso plantas energía luz",
    "Capital de Francia población cultura",
    "Los métodos de optimización en deep learning",
]

# ── Path B: TF-IDF ───────────────────────────────────────────────────────


class TestPathBTfIdf:
    def _make_chunks(self) -> list[SearchResult]:
        return [
            _chunk(f"/docs/topic_{i}.txt", 0, content)
            for i, content in enumerate(MULTI_CHUNK_CONTENTS)
        ]

    def test_compressor_returns_search_results(self):
        compressor = SemanticCompressor(embed_fn=None)
        chunks = self._make_chunks()
        result = compressor.compress("gradient descent", chunks, max_tokens=600)
        assert isinstance(result, list)
        assert all(isinstance(c, SearchResult) for c in result)

    def test_token_budget_respected(self):
        compressor = SemanticCompressor(embed_fn=None)
        chunks = self._make_chunks()
        for query in TEST_QUERIES:
            compressed = compressor.compress(query, chunks, max_tokens=600)
            total = sum(_estimated_tokens(c.content) for c in compressed)
            assert total <= 600, f"Query '{query[:30]}': {total} tokens > 600"

    def test_compression_ratio(self):
        compressor = SemanticCompressor(embed_fn=None)
        chunks = self._make_chunks()
        input_tokens = sum(_estimated_tokens(c.content) for c in chunks)
        ratios = []
        for query in TEST_QUERIES:
            compressed = compressor.compress(query, chunks, max_tokens=600)
            output_tokens = sum(_estimated_tokens(c.content) for c in compressed)
            ratio = (input_tokens - output_tokens) / input_tokens * 100
            ratios.append(ratio)
        avg_ratio = sum(ratios) / len(ratios)
        assert avg_ratio > 30, f"Average compression ratio {avg_ratio:.1f}% < 30%"

    def test_lineage_preservation(self):
        chunks = [
            _chunk(
                "/docs/math.txt",
                0,
                "Derivatives measure rates of change. The chain rule is essential.",
            ),
            _chunk(
                "/docs/math.txt",
                1,
                "Integrals compute areas under curves. They are the inverse of derivatives.",
            ),
            _chunk(
                "/docs/physics.txt",
                0,
                "Quantum mechanics describes particles. Wave functions encode probabilities.",
            ),
        ]
        original_lineage = {(c.source_path, c.chunk_index) for c in chunks}
        compressor = SemanticCompressor(embed_fn=None)
        compressed = compressor.compress("calculus derivatives", chunks, max_tokens=600)
        compressed_lineage = {(c.source_path, c.chunk_index) for c in compressed}
        assert compressed_lineage.issubset(
            original_lineage
        ), f"Compressed lineage {compressed_lineage} not subset of original {original_lineage}"

    def test_chronological_order(self):
        sentences = [
            f"Oración {i} con contenido de relleno para probar que el compresor mantiene el orden."
            for i in range(1, 13)
        ]
        content = " ".join(sentences)
        chunks = [_chunk("/docs/test.txt", 0, content)]
        compressor = SemanticCompressor(embed_fn=None)
        compressed = compressor.compress("orden cronológico oraciones", chunks, max_tokens=600)
        nums = [int(m) for m in re.findall(r"Oración (\d+)", compressed[0].content)]
        assert all(
            nums[i] < nums[i + 1] for i in range(len(nums) - 1)
        ), f"Order not ascending: {nums}"

    def test_hard_filters_min_tokens(self):
        chunks = [
            _chunk("/docs/test.txt", 0, "Hi. A. B. C. This is a valid sentence with enough tokens.")
        ]
        compressor = SemanticCompressor(embed_fn=None)
        compressed = compressor.compress("valid sentence", chunks, max_tokens=600)
        assert "This is a valid sentence" in compressed[0].content
        assert "Hi" not in compressed[0].content.split(". ")

    def test_hard_filters_fillers(self):
        chunks = [
            _chunk(
                "/docs/test.txt",
                0,
                "However, this is important context. In addition, more content. "
                "The capital of France is Paris, a real fact.",
            )
        ]
        compressor = SemanticCompressor(embed_fn=None)
        compressed = compressor.compress("capital of France", chunks, max_tokens=600)
        assert "capital of France" in compressed[0].content

    def test_empty_chunks_returns_empty(self):
        compressor = SemanticCompressor(embed_fn=None)
        result = compressor.compress("anything", [], max_tokens=600)
        assert result == []

    def test_multilingual_support(self):
        chunks = [
            _chunk(
                "/docs/en.txt",
                0,
                "Gradient descent is an optimization algorithm. It is widely used in ML.",
            ),
            _chunk(
                "/docs/es.txt",
                0,
                "El descenso de gradiente es un algoritmo de optimización. Se usa en ML.",
            ),
        ]
        compressor = SemanticCompressor(embed_fn=None)
        en_result = compressor.compress("gradient descent optimization", chunks, max_tokens=600)
        es_result = compressor.compress(
            "descenso de gradiente optimización", chunks, max_tokens=600
        )
        assert len(en_result) > 0
        assert len(es_result) > 0

    def test_memory_profile(self):
        chunks = self._make_chunks()
        compressor = SemanticCompressor(embed_fn=None)
        tracemalloc.start()
        for _ in range(5):
            compressor.compress("test query", chunks, max_tokens=600)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert peak < 50 * 1024 * 1024, f"Peak memory {peak/1024/1024:.2f} MB > 50 MB"

    def test_latency(self):
        chunks = self._make_chunks()
        compressor = SemanticCompressor(embed_fn=None)
        start = time.monotonic()
        for query in TEST_QUERIES:
            compressor.compress(query, chunks, max_tokens=600)
        elapsed = time.monotonic() - start
        avg_ms = elapsed / len(TEST_QUERIES) * 1000
        assert avg_ms < 50, f"Average latency {avg_ms:.1f}ms per query ≥ 50ms"

    def test_no_mid_sentence_cuts(self):
        long_content = (
            "Machine learning is a subset of artificial intelligence. "
            "It involves training models on data to make predictions. "
            "Supervised learning uses labeled training data. "
            "Unsupervised learning finds patterns in unlabeled data. "
            "Reinforcement learning uses rewards and punishments. "
            "Deep learning uses neural networks with many layers. "
            "Each of these approaches has unique strengths and weaknesses. "
            "The choice depends on the specific problem and data available."
        )
        chunks = [_chunk("/docs/test.txt", 0, long_content)]
        compressor = SemanticCompressor(embed_fn=None)
        compressed = compressor.compress("machine learning", chunks, max_tokens=100)
        assert compressed[0].content.endswith(
            "."
        ), f"Content ends mid-sentence: ...{compressed[0].content[-50:]}"


# ── Path A: Neural (mocked llama.cpp embeddings) ─────────────────────────


class TestPathANeural:
    def _make_embed_fn(self, dim: int = 384) -> callable:
        def _fake_embed(texts: list[str]) -> np.ndarray:
            return np.random.randn(len(texts), dim).astype(np.float32)

        return _fake_embed

    def test_compressor_returns_search_results_with_embeddings(self):
        compressor = SemanticCompressor(embed_fn=self._make_embed_fn())
        chunks = [
            _chunk("/docs/test.txt", 0, "The capital of France is Paris. It is a beautiful city.")
        ]
        result = compressor.compress("capital of France", chunks, max_tokens=600)
        assert isinstance(result, list)
        assert all(isinstance(c, SearchResult) for c in result)

    def test_token_budget_with_embeddings(self):
        embed_fn = self._make_embed_fn()
        compressor = SemanticCompressor(embed_fn=embed_fn)
        chunks = [
            _chunk(f"/docs/topic_{i}.txt", 0, content)
            for i, content in enumerate(MULTI_CHUNK_CONTENTS)
        ]
        for query in TEST_QUERIES:
            compressed = compressor.compress(query, chunks, max_tokens=600)
            total = sum(_estimated_tokens(c.content) for c in compressed)
            assert total <= 600, f"Query '{query[:30]}': {total} tokens > 600"

    def test_lineage_with_embeddings(self):
        embed_fn = self._make_embed_fn()
        chunks = [
            _chunk(
                "/docs/math.txt",
                0,
                "Derivatives measure rates of change. The chain rule is essential.",
            ),
            _chunk("/docs/math.txt", 1, "Integrals compute areas under curves."),
            _chunk("/docs/physics.txt", 0, "Quantum mechanics describes particles."),
        ]
        original_lineage = {(c.source_path, c.chunk_index) for c in chunks}
        compressor = SemanticCompressor(embed_fn=embed_fn)
        compressed = compressor.compress("calculus derivatives", chunks, max_tokens=600)
        compressed_lineage = {(c.source_path, c.chunk_index) for c in compressed}
        assert compressed_lineage.issubset(original_lineage)

    def test_chronological_order_with_embeddings(self):
        embed_fn = self._make_embed_fn()
        sentences = [
            f"Sentence {i} with some content for order testing purposes." for i in range(1, 11)
        ]
        content = " ".join(sentences)
        chunks = [_chunk("/docs/test.txt", 0, content)]
        compressor = SemanticCompressor(embed_fn=embed_fn)
        compressed = compressor.compress("order testing", chunks, max_tokens=600)
        nums = [int(m) for m in re.findall(r"Sentence (\d+)", compressed[0].content)]
        assert all(nums[i] < nums[i + 1] for i in range(len(nums) - 1)), f"Not ascending: {nums}"

    def test_mocked_llamacpp_embed_endpoint(self):
        """Simulate calling a real llama.cpp /v1/embeddings endpoint via httpx,
        but mocked at the HTTP level."""
        fake_embedding = [0.1] * 384
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"embedding": fake_embedding}]}

        def mock_post(url, json, timeout):
            return mock_response

        with patch("httpx.post", side_effect=mock_post):
            import httpx

            resp = httpx.post(
                "http://127.0.0.1:8080/v1/embeddings",
                json={"model": "default", "input": "test"},
                timeout=30.0,
            )
            data = resp.json()
            emb = data["data"][0]["embedding"]
            assert len(emb) == 384

    def test_async_embed_fn_auto_wrapping(self):
        """Async embed functions are automatically wrapped."""

        async def async_embed(texts: list[str]) -> np.ndarray:
            emb = np.zeros((len(texts), 384), dtype=np.float32)
            emb[:, 0] = 1.0
            return emb

        compressor = SemanticCompressor(embed_fn=async_embed)
        chunks = [_chunk("/docs/test.txt", 0, "The capital of France is Paris. Beautiful city.")]
        result = compressor.compress("capital of France", chunks, max_tokens=600)
        assert len(result) > 0
        assert isinstance(result[0], SearchResult)

    def test_no_mid_sentence_cuts_with_embeddings(self):
        embed_fn = self._make_embed_fn()
        long_content = (
            "Machine learning is a subset of artificial intelligence. "
            "It involves training models on data to make predictions. "
            "Supervised learning uses labeled training data. "
            "Unsupervised learning finds patterns in unlabeled data. "
            "Reinforcement learning uses rewards and punishments. "
            "Deep learning uses neural networks with many layers. "
        )
        chunks = [_chunk("/docs/test.txt", 0, long_content)]
        compressor = SemanticCompressor(embed_fn=embed_fn)
        compressed = compressor.compress("machine learning", chunks, max_tokens=100)
        assert compressed[0].content.endswith(
            "."
        ), f"Content ends mid-sentence: ...{compressed[0].content[-50:]}"


# ── Integration: RAGQueryEngine + SemanticCompressor ────────────────────


class TestRAGIntegration:
    @pytest.mark.asyncio
    async def test_rag_with_compressor_tfidf(self):
        from unittest.mock import AsyncMock

        from core.inference.engine import InferenceEngine
        from core.memory.vector_store import VectorStore
        from core.rag.query_engine import RAGQueryEngine

        store = AsyncMock(spec=VectorStore)
        store.search = AsyncMock(
            return_value=[
                _chunk(
                    "/docs/notes.txt",
                    0,
                    "The capital of France is Paris. Paris is a major European city.",
                ),
                _chunk(
                    "/docs/notes.txt",
                    1,
                    "France is located in Western Europe. It borders several countries.",
                ),
            ]
        )
        engine = AsyncMock(spec=InferenceEngine)
        engine.complete = AsyncMock(return_value="Paris is the capital of France.")
        compressor = SemanticCompressor(embed_fn=None)
        rag = RAGQueryEngine(store=store, engine=engine, compressor=compressor)
        response = await rag.query("What is the capital of France?")
        assert response.answer == "Paris is the capital of France."
        assert response.chunks_used > 0

    @pytest.mark.asyncio
    async def test_rag_with_compressor_neural(self):
        from unittest.mock import AsyncMock

        import numpy as np

        from core.inference.engine import InferenceEngine
        from core.memory.vector_store import VectorStore
        from core.rag.query_engine import RAGQueryEngine

        store = AsyncMock(spec=VectorStore)
        store.search = AsyncMock(
            return_value=[
                _chunk(
                    "/docs/notes.txt",
                    0,
                    "The capital of France is Paris. Paris is a major European city.",
                ),
            ]
        )
        engine = AsyncMock(spec=InferenceEngine)
        engine.complete = AsyncMock(return_value="Paris.")

        def deterministic_embed(texts: list[str]) -> np.ndarray:
            emb = np.zeros((len(texts), 384), dtype=np.float32)
            emb[:, 0] = 1.0
            return emb

        compressor = SemanticCompressor(embed_fn=deterministic_embed)
        rag = RAGQueryEngine(store=store, engine=engine, compressor=compressor)
        response = await rag.query("Capital of France?")
        assert response.answer == "Paris."
        assert response.chunks_used > 0

    @pytest.mark.asyncio
    async def test_rag_without_compressor_still_works(self):
        from unittest.mock import AsyncMock

        from core.inference.engine import InferenceEngine
        from core.memory.vector_store import VectorStore
        from core.rag.query_engine import RAGQueryEngine

        store = AsyncMock(spec=VectorStore)
        store.search = AsyncMock(
            return_value=[_chunk("/docs/notes.txt", 0, "Paris is the capital.")]
        )
        engine = AsyncMock(spec=InferenceEngine)
        engine.complete = AsyncMock(return_value="Paris.")
        rag = RAGQueryEngine(store=store, engine=engine)
        response = await rag.query("Capital?")
        assert response.answer == "Paris."

    @pytest.mark.asyncio
    async def test_rag_compressed_flag_true_when_compressor_reduces_chunks(self):
        from unittest.mock import AsyncMock

        from core.inference.engine import InferenceEngine
        from core.memory.vector_store import VectorStore
        from core.rag.query_engine import RAGQueryEngine

        store = AsyncMock(spec=VectorStore)
        store.search = AsyncMock(
            return_value=[
                _chunk(
                    "/docs/notes.txt",
                    0,
                    "The capital of France is Paris. Paris is a major European city.",
                ),
                _chunk(
                    "/docs/other.txt",
                    0,
                    "Irrelevant content about cooking pasta with tomatoes and herbs.",
                ),
            ]
        )
        engine = AsyncMock(spec=InferenceEngine)
        engine.complete = AsyncMock(return_value="Paris.")
        compressor = SemanticCompressor(embed_fn=None)
        rag = RAGQueryEngine(store=store, engine=engine, compressor=compressor)
        response = await rag.query("Capital of France?")
        assert response.compressed is True

    @pytest.mark.asyncio
    async def test_rag_compressed_flag_false_without_compressor(self):
        from unittest.mock import AsyncMock

        from core.inference.engine import InferenceEngine
        from core.memory.vector_store import VectorStore
        from core.rag.query_engine import RAGQueryEngine

        store = AsyncMock(spec=VectorStore)
        store.search = AsyncMock(
            return_value=[_chunk("/docs/notes.txt", 0, "Paris is the capital.")]
        )
        engine = AsyncMock(spec=InferenceEngine)
        engine.complete = AsyncMock(return_value="Paris.")
        rag = RAGQueryEngine(store=store, engine=engine)
        response = await rag.query("Capital?")
        assert response.compressed is False


# ── Unit: SentenceUnit and helpers ───────────────────────────────────────


class TestSentenceUnit:
    def test_sentence_unit_creation(self):
        unit = SentenceUnit(
            text="Hello world.",
            source_path="/docs/test.txt",
            chunk_index=0,
            original_position=0,
        )
        assert unit.text == "Hello world."
        assert unit.source_path == "/docs/test.txt"
        assert unit.chunk_index == 0
        assert unit.original_position == 0
        assert unit.score == 0.0

    def test_sentence_unit_score_mutable(self):
        unit = SentenceUnit(
            text="Test.", source_path="/docs/x.txt", chunk_index=0, original_position=0
        )
        unit.score = 0.95
        assert unit.score == 0.95


# ── Run and record results ──────────────────────────────────────────────


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
