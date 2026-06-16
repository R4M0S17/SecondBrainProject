"""Semantic context compressor for high-density RAG context assembly.

Intercepts raw SearchResult chunks immediately after retrieval from LanceDB,
decomposes them into sentence-level atomic units, and reconstructs a
token-budget-bounded, semantically dense context block.
"""

from __future__ import annotations

import asyncio
import inspect
import re
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from core.memory.vector_store import SearchResult


@dataclass
class SentenceUnit:
    """Atomic sentence extracted from a SearchResult chunk.

    Preserves full RAG lineage so that downstream consumers
    (query_engine.py, prompt.py) can reconstruct source attribution
    without any schema changes to SearchResult.
    """

    text: str  # Raw sentence text (stripped)
    source_path: str  # Inherited directly from parent SearchResult.source_path
    chunk_index: int  # Inherited directly from parent SearchResult.chunk_index
    original_position: int  # 0-based ordinal within the parent chunk's sentence list
    score: float = 0.0  # Relevance score assigned during Step 3.2; default 0.0


class SemanticCompressor:
    """Intercepts raw SearchResult chunks and returns a token-budget-bounded,
    semantically dense subset, preserving original reading order within each chunk.

    Args:
        embed_fn: Optional callable that accepts a list[str] and returns an
                  np.ndarray of shape (N, D). When provided, cosine similarity
                  is used for scoring (Option A). When None, a TF-IDF/BM25
                  lexical scorer is constructed on first call (Option B).
        min_sentence_tokens: Sentences shorter than this token estimate are
                             discarded as non-informative fragments.
    """

    # Compiled regex for sentence splitting:
    # Python's re module doesn't support variable-width lookbehinds, so we use
    # alternation to handle optional quotes after sentence-terminal punctuation.
    # Matches: (punct + optional quote + space + uppercase) OR newlines
    # See Section 3.1 of semantic_context_compressor.md for specification.
    _SENTENCE_SPLIT_RE = re.compile(
        r'(?<!\d)(?<!\w\.\w)(?<=[.!?…]["»\'])\s+(?=[A-ZÁÉÍÓÚÑ"])'
        r'|(?<!\d)(?<!\w\.\w)(?<=[.!?…])\s+(?=[A-ZÁÉÍÓÚÑ"])'
        r"|\n+"
    )

    # Filler / connector phrase prefixes — case-insensitive matching during filtering.
    # See Step 3.3 Phase A of semantic_context_compressor.md.
    _FILLER_PREFIXES: frozenset[str] = frozenset(
        {
            "además",
            "también",
            "sin embargo",
            "por otro lado",
            "en conclusión",
            "en resumen",
            "como se mencionó",
            "cabe destacar",
            "es importante",
            "hay que señalar",
            "in addition",
            "furthermore",
            "however",
            "moreover",
            "in conclusion",
            "in summary",
            "as mentioned",
            "it is worth",
            "it should be noted",
        }
    )

    # Token budget reserved per chunk for header overhead (e.g. "[Fuente: ..., chunk N]\n").
    _HEADER_TOKENS: int = 10

    # Regex matching strings composed entirely of non-word / digit / whitespace characters.
    _PUNCTUATION_ONLY_RE = re.compile(r"[\W\d\s]+")

    def __init__(
        self,
        embed_fn: Callable[[list[str]], np.ndarray] | None = None,
        min_sentence_tokens: int = 5,
    ) -> None:
        """Initialize the SemanticCompressor.

        Args:
            embed_fn: Optional embedding function for neural scoring.
                      If async (coroutine function), it is automatically wrapped
                      in a synchronous adapter via asyncio.run().
            min_sentence_tokens: Minimum token count threshold for sentence retention.
        """
        if embed_fn is not None and inspect.iscoroutinefunction(embed_fn):
            _original = embed_fn

            def _sync_wrapper(texts: list[str]) -> np.ndarray:
                return asyncio.run(_original(texts))

            self.embed_fn = _sync_wrapper
        else:
            self.embed_fn = embed_fn
        self.min_sentence_tokens = min_sentence_tokens

    def _score_via_neural_similarity(
        self, all_sentence_units: list[SentenceUnit], query: str
    ) -> None:
        """Path A: Assign scores using neural embeddings and cosine similarity.

        Modifies all_sentence_units in-place by setting unit.score for each item.
        """
        if not all_sentence_units:
            return

        # Collect all sentence texts and prepend the query
        texts = [query] + [unit.text for unit in all_sentence_units]

        # Call embed_fn (single batched call for all texts)
        embeddings = self.embed_fn(texts)  # shape: (N+1, D)

        # Isolate query and sentence vectors
        query_vec = embeddings[0]  # shape: (D,)
        sentence_vecs = embeddings[1:]  # shape: (N, D)

        # L2-normalize all vectors
        query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-9)
        sentence_norms = sentence_vecs / (
            np.linalg.norm(sentence_vecs, axis=1, keepdims=True) + 1e-9
        )

        # Compute dot product (cosine similarity)
        scores = sentence_norms @ query_norm  # shape: (N,)

        # Assign scores to each SentenceUnit
        for i, unit in enumerate(all_sentence_units):
            unit.score = float(scores[i])

    def _score_via_tfidf(self, all_sentence_units: list[SentenceUnit], query: str) -> None:
        """Path B: Assign scores using TF-IDF lexical similarity.

        Modifies all_sentence_units in-place by setting unit.score for each item.
        """
        if not all_sentence_units:
            return

        # Define local tokenizer
        def tokenize(text: str) -> list[str]:
            return re.findall(r"[a-záéíóúñ\w]+", text.lower())

        # Tokenize all sentences and the query
        sentence_tokens = [tokenize(unit.text) for unit in all_sentence_units]
        query_tokens = tokenize(query)

        # Build vocabulary from all tokens
        all_tokens = set()
        for tokens in sentence_tokens:
            all_tokens.update(tokens)
        all_tokens.update(query_tokens)

        vocab = sorted(all_tokens)
        vocab_index = {token: i for i, token in enumerate(vocab)}
        V = len(vocab)
        N = len(all_sentence_units)

        # Construct term-frequency matrix: shape (N, V)
        tf = np.zeros((N, V), dtype=np.float32)
        for i, tokens in enumerate(sentence_tokens):
            for token in tokens:
                j = vocab_index[token]
                tf[i, j] += 1.0

        # Compute document frequency and IDF
        df = np.sum(tf > 0, axis=0)  # shape: (V,)
        idf = np.log((N + 1) / (1 + df))  # shape: (V,)

        # Compute TF-IDF matrix
        tfidf = tf * idf  # broadcast: (N, V) * (V,) -> (N, V)

        # Compute query TF-IDF vector using the same vocabulary and IDF
        query_tf = np.zeros(V, dtype=np.float32)
        for token in query_tokens:
            if token in vocab_index:
                j = vocab_index[token]
                query_tf[j] += 1.0
        query_tfidf = query_tf * idf  # shape: (V,)

        # Compute cosine similarity
        tfidf_norms = np.linalg.norm(tfidf, axis=1)  # shape: (N,)
        query_norm = np.linalg.norm(query_tfidf)  # scalar
        denominator = tfidf_norms * query_norm + 1e-9
        scores = (tfidf @ query_tfidf) / denominator  # shape: (N,)

        # Assign scores to each SentenceUnit
        for i, unit in enumerate(all_sentence_units):
            unit.score = float(scores[i])

    @staticmethod
    def _estimated_tokens(text: str) -> int:
        return max(1, len(text) // 4)

    def _is_filler(self, text: str) -> bool:
        lower = text.lower()
        return any(lower.startswith(p) for p in self._FILLER_PREFIXES)

    def compress(
        self,
        query: str,
        chunks: list[SearchResult],
        max_tokens: int = 800,
    ) -> list[SearchResult]:
        """Public entry point. Returns a list[SearchResult] whose `.content`
        fields have been replaced with compressed, high-density text.
        The `.source_path` and `.chunk_index` fields are NEVER mutated.

        The returned list is a strict subset reconstruction: callers receive
        standard SearchResult objects and require no schema awareness of
        SentenceUnit internals.

        Args:
            query: The user query for relevance scoring.
            chunks: List of SearchResult objects retrieved from LanceDB.
            max_tokens: Maximum token budget for compressed output (~600 tokens ≈ 2,400 chars).

        Returns:
            List of SearchResult objects with compressed content.
        """
        # =====================================================================
        # STEP 3.1 — Sentence Tokenization
        # =====================================================================
        # Decompose each chunk.content into SentenceUnit objects using
        # punctuation-aware regex splitting.

        all_sentence_units: list[SentenceUnit] = []

        for chunk in chunks:
            # Split chunk content into sentences using the compiled regex
            raw_sentences = self._SENTENCE_SPLIT_RE.split(chunk.content)

            # Filter empty sentences and create SentenceUnit objects
            sentence_index = 0
            for raw_sentence in raw_sentences:
                stripped = raw_sentence.strip()
                if stripped:  # Only keep non-empty sentences
                    unit = SentenceUnit(
                        text=stripped,
                        source_path=chunk.source_path,
                        chunk_index=chunk.chunk_index,
                        original_position=sentence_index,
                    )
                    all_sentence_units.append(unit)
                    sentence_index += 1

        # =====================================================================
        # STEP 3.2 — Scoring / Vectorization
        # =====================================================================
        if self.embed_fn is not None:
            self._score_via_neural_similarity(all_sentence_units, query)
        else:
            self._score_via_tfidf(all_sentence_units, query)

        # =====================================================================
        # STEP 3.3 — Entropy / Information Density Filtering
        # =====================================================================

        # Phase A — Hard Filters (applied before score comparison)
        survivors: list[SentenceUnit] = []
        for unit in all_sentence_units:
            if self._estimated_tokens(unit.text) < self.min_sentence_tokens:
                continue
            if self._PUNCTUATION_ONLY_RE.fullmatch(unit.text):
                continue
            if self._is_filler(unit.text):
                continue
            survivors.append(unit)

        # Phase B — Adaptive Thresholding
        if survivors:
            mean_score = float(np.mean([u.score for u in survivors]))
            threshold = mean_score * 0.5
            survivors = [u for u in survivors if u.score >= threshold]

        # Phase C — Chronological Reconstruction
        groups: dict[tuple[str, int], list[SentenceUnit]] = {}
        for unit in survivors:
            key = (unit.source_path, unit.chunk_index)
            if key not in groups:
                groups[key] = []
            groups[key].append(unit)

        for group in groups.values():
            group.sort(key=lambda u: u.original_position)

        # =====================================================================
        # STEP 3.4 — Token-Budget Assembly
        # =====================================================================
        budget_remaining = max_tokens
        output_chunks: list[SearchResult] = []

        for chunk in chunks:
            key = (chunk.source_path, chunk.chunk_index)
            if key not in groups:
                continue
            sentences = groups[key]

            header_cost = self._HEADER_TOKENS
            if budget_remaining - header_cost < 0:
                break
            budget_remaining -= header_cost

            accepted_texts: list[str] = []
            for unit in sentences:
                sentence_cost = self._estimated_tokens(unit.text) + 1
                if budget_remaining - sentence_cost < 0:
                    break
                accepted_texts.append(unit.text)
                budget_remaining -= sentence_cost

            if accepted_texts:
                joined = " ".join(accepted_texts)
                output_chunks.append(
                    SearchResult(
                        id=chunk.id,
                        content=joined,
                        source_path=chunk.source_path,
                        chunk_index=chunk.chunk_index,
                        score=chunk.score,
                        metadata=chunk.metadata,
                    )
                )

        return output_chunks
