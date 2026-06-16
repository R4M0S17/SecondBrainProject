from __future__ import annotations

import asyncio
import collections.abc
import subprocess
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from loguru import logger

from core.knowledge_sync.models import FetchedItem

_SLM_MODEL = "Qwen2.5-0.5B-Instruct-Q5_K_M.gguf"
_SLM_URL = "http://127.0.0.1:8081"
_SLM_PROCESS: subprocess.Popen | None = None


class ContentFilter:
    def __init__(
        self,
        embed_provider: Any,
        interest_tags: list[str] | None = None,
        relevance_threshold: float = 0.6,
        dedup_threshold: float = 0.4,
    ) -> None:
        self._embed = getattr(embed_provider, "embed", embed_provider)
        self._interest_tags = interest_tags or []
        self._relevance_threshold = relevance_threshold
        self._dedup_threshold = dedup_threshold
        self._tag_vectors: list[list[float]] | None = None

    async def _ensure_tag_vectors(self) -> None:
        if self._tag_vectors is not None or not self._interest_tags:
            return
        tag_texts = [f"tag: {t}" for t in self._interest_tags]
        results = await asyncio.gather(*[self._embed(t) for t in tag_texts])
        self._tag_vectors = results

    async def filter(
        self,
        items: list[FetchedItem],
        vector_store: Any,
        is_manual_trigger: bool = False,
    ) -> list[FetchedItem]:
        if not items:
            return []
        await self._ensure_tag_vectors()

        if self._tag_vectors and self._interest_tags:
            items = await self._filter_by_embedding(items)
        if not items:
            return []

        items = await self._filter_dedup(items, vector_store)
        if not items:
            return []

        if is_manual_trigger or len(items) <= 2:
            items = await self._filter_novelty_slm(items)

        return items

    async def _filter_by_embedding(self, items: list[FetchedItem]) -> list[FetchedItem]:
        texts = [f"{item.title} {item.summary or item.content[:200]}" for item in items]
        item_vectors = await asyncio.gather(*[self._embed(t) for t in texts])

        tag_arr = np.array(self._tag_vectors, dtype=np.float32)
        item_arr = np.array(item_vectors, dtype=np.float32)

        scores = item_arr @ tag_arr.T
        max_scores = scores.max(axis=1)

        kept = [item for i, item in enumerate(items) if max_scores[i] >= self._relevance_threshold]
        logger.debug(
            "Layer 1: {}/{} items passed relevance filter (threshold={})",
            len(kept),
            len(items),
            self._relevance_threshold,
        )
        return kept

    async def _filter_dedup(
        self,
        items: list[FetchedItem],
        vector_store: Any,
    ) -> list[FetchedItem]:
        indexed: dict[str, float] = {}
        try:
            if hasattr(vector_store, "get_indexed_files") and callable(
                vector_store.get_indexed_files
            ):
                maybe = vector_store.get_indexed_files()
                indexed = await maybe if isinstance(maybe, collections.abc.Awaitable) else maybe
        except Exception:
            pass

        kept: list[FetchedItem] = []
        for item in items:
            if item.url in indexed:
                logger.debug(
                    "Layer 2: dedup skipped '{}' (exact URL already indexed)",
                    item.title,
                )
                continue

            text = f"{item.title} {item.summary or item.content[:200]}"
            vec = await self._embed(text)
            existing = await vector_store.search_by_vector(vec, top_k=1)
            if existing and existing[0].score <= self._dedup_threshold:
                logger.debug(
                    "Layer 2: dedup skipped '{}' (distance={:.3f})",
                    item.title,
                    existing[0].score,
                )
                continue
            kept.append(item)
        logger.debug("Layer 2: {}/{} items passed dedup", len(kept), len(items))
        return kept

    async def _filter_novelty_slm(self, items: list[FetchedItem]) -> list[FetchedItem]:
        kept: list[FetchedItem] = []
        for item in items:
            prompt = (
                f"Artículo: {item.title}\n\n"
                f"{item.summary or item.content[:500]}\n\n"
                "Responde SOLO con una de estas etiquetas:\n"
                "- NOVEDAD_ALTA: información nueva y relevante\n"
                "- NOVEDAD_MEDIA: complementa conocimiento existente\n"
                "- NOVEDAD_BAJA: ya conocido o irrelevante"
            )
            try:
                label = await _slm_complete(prompt, max_tokens=32)
                if not label:
                    kept.append(item)
                    continue
                item.metadata["novelty_label"] = label.strip().upper()
                if "ALTA" in item.metadata["novelty_label"]:
                    kept.append(item)
                elif "MEDIA" in item.metadata["novelty_label"]:
                    kept.append(item)
            except Exception as exc:
                logger.warning("SLM novelty scoring failed for '{}': {}", item.title, exc)
                kept.append(item)
        return kept


async def _ensure_slm_engine(bin_dir: str = "bin") -> bool:
    global _SLM_PROCESS
    if _SLM_PROCESS is not None and _SLM_PROCESS.poll() is None:
        try:
            async with httpx.AsyncClient(timeout=2.0) as c:
                r = await c.get(f"{_SLM_URL}/health")
                return r.status_code == 200
        except httpx.ConnectError:
            pass

    model_path = Path(bin_dir) / "models" / _SLM_MODEL
    if not model_path.is_file():
        logger.error("SLM model not found: {}", model_path)
        return False

    import psutil

    free = psutil.virtual_memory().available / (1024**3)
    if free < 0.5:
        logger.warning("Insufficient RAM ({:.1f} GB) to start SLM engine", free)
        return False

    args_path = Path(bin_dir) / "start_engine.sh"
    _SLM_PROCESS = subprocess.Popen(
        [
            "bash",
            str(args_path),
            "chat",
            "--port",
            "8081",
            "--model",
            _SLM_MODEL,
            "--ctx-size",
            "2048",
            "--n-gpu-layers",
            "0",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(30):
        await asyncio.sleep(0.5)
        try:
            async with httpx.AsyncClient(timeout=1.0) as c:
                r = await c.get(f"{_SLM_URL}/health")
                if r.status_code == 200:
                    return True
        except httpx.ConnectError:
            continue
    return False


async def _slm_complete(prompt: str, max_tokens: int = 256) -> str:
    if not await _ensure_slm_engine():
        return ""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{_SLM_URL}/v1/chat/completions",
            json={
                "model": _SLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.3,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()


async def _slm_shutdown() -> None:
    global _SLM_PROCESS
    if _SLM_PROCESS is not None:
        _SLM_PROCESS.terminate()
        try:
            await asyncio.wait_for(_slm_wait(), timeout=5.0)
        except TimeoutError:
            _SLM_PROCESS.kill()
        _SLM_PROCESS = None


async def _slm_wait() -> None:
    while _SLM_PROCESS is not None and _SLM_PROCESS.poll() is None:
        await asyncio.sleep(0.1)
