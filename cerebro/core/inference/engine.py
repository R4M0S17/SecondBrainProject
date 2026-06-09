from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
from loguru import logger

# Non-streaming inference: generous read window for long prompts.
_TIMEOUT_COMPLETE = httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=5.0)

# Embedding: embeddings are fast; short read window.
_TIMEOUT_EMBED = httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0)

# Streaming: read=None disables per-read timeout; connection stays alive
# as long as tokens keep arriving.
_TIMEOUT_STREAM = httpx.Timeout(connect=5.0, read=None, write=10.0, pool=5.0)


async def _guarded_token_iter(
    aiter,
    stall_timeout_s: float,
) -> AsyncIterator[str]:
    while True:
        try:
            line = await asyncio.wait_for(anext(aiter), timeout=stall_timeout_s)
        except TimeoutError as e:
            raise InferenceTimeoutError(
                f"llama-server stalled: no token for {stall_timeout_s}s"
            ) from e
        except StopAsyncIteration:
            break
        yield line


class InferenceTimeoutError(Exception):
    pass


class ModelNotFoundError(Exception):
    pass


class LlamaCppUnavailableError(Exception):
    pass


@dataclass
class StreamDone:
    slot_id: int | None = None
    tokens_predicted: int = 0
    timings: dict | None = None


class InferenceEngine:
    EMBEDDING_MODEL = "nomic-embed-text"

    def __init__(
        self,
        model: str,
        base_url: str = "http://127.0.0.1:8080",
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._shared_client: httpx.AsyncClient | None = http_client

    @asynccontextmanager
    async def _client(
        self,
        timeout: httpx.Timeout | None = None,
    ) -> AsyncIterator[httpx.AsyncClient]:
        if self._shared_client is not None:
            yield self._shared_client
        else:
            effective_timeout = timeout or httpx.Timeout(30.0)
            async with httpx.AsyncClient(timeout=effective_timeout) as client:
                yield client

    async def complete(self, prompt: str, system: str = "") -> str:
        payload: dict = {"model": self.model, "prompt": prompt, "stream": False}
        if system:
            payload["system"] = system

        try:
            async with self._client(_TIMEOUT_COMPLETE) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=_TIMEOUT_COMPLETE,
                )
                if response.status_code == 404:
                    raise ModelNotFoundError(f"Model '{self.model}' not found")
                response.raise_for_status()
                data = response.json()
                return str(data["response"]).strip()
        except httpx.TimeoutException as e:
            raise InferenceTimeoutError("llama.cpp timed out") from e
        except httpx.ConnectError as e:
            raise LlamaCppUnavailableError(f"Cannot connect to llama.cpp at {self.base_url}") from e

    async def embed(self, text: str) -> list[float]:
        payload = {"model": self.EMBEDDING_MODEL, "prompt": text}

        try:
            async with self._client(_TIMEOUT_EMBED) as client:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json=payload,
                    timeout=_TIMEOUT_EMBED,
                )
                if response.status_code == 404:
                    raise ModelNotFoundError(f"Embedding model '{self.EMBEDDING_MODEL}' not found")
                response.raise_for_status()
                raw_emb = response.json()["embedding"]
                return [float(x) for x in raw_emb]
        except httpx.TimeoutException as e:
            raise InferenceTimeoutError("Embedding timed out") from e
        except httpx.ConnectError as e:
            raise LlamaCppUnavailableError(f"Cannot connect to llama.cpp at {self.base_url}") from e

    async def stream(
        self,
        prompt: str,
        *,
        slot_id: int | None = None,
        stall_timeout_s: float = 60.0,
    ) -> AsyncIterator[str | StreamDone]:
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
        }
        if slot_id is not None:
            payload["slot_id"] = slot_id

        try:
            async with self._client(_TIMEOUT_STREAM) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=_TIMEOUT_STREAM,
                ) as response:
                    response.raise_for_status()
                    lines_iter = response.aiter_lines().__aiter__()
                    async for line in _guarded_token_iter(lines_iter, stall_timeout_s):
                        if not line:
                            continue
                        data = json.loads(line)
                        if token := data.get("response"):
                            yield token
                        if data.get("done"):
                            yield StreamDone(
                                slot_id=data.get("slot_id"),
                                tokens_predicted=data.get("tokens_predicted", 0),
                                timings=data.get("timings"),
                            )
                            break
        except asyncio.CancelledError:
            logger.debug("stream() cancelled — releasing connection to pool")
            raise
        except httpx.ConnectError as e:
            raise LlamaCppUnavailableError(f"Cannot connect to llama.cpp at {self.base_url}") from e

    def is_available(self) -> bool:
        try:
            with httpx.Client(timeout=httpx.Timeout(5.0)) as client:
                response = client.get(f"{self.base_url}/health")
                return int(response.status_code) == 200
        except Exception:
            logger.debug("llama.cpp unavailable at {}", self.base_url)
            return False
