from __future__ import annotations

from typing import Any, cast

import httpx

from core.inference.engine import InferenceTimeoutError


class LlamaCppEmbeddingProvider:
    DIMENSIONS = 1024  # jina-embeddings-v5-text-nano

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8082",
        model: str = "jina-embeddings",
        timeout: int = 30,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = httpx.Timeout(float(timeout))

    async def embed(self, text: str) -> list[float]:
        payload = {"model": self._model, "input": [text]}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(f"{self._base_url}/v1/embeddings", json=payload)
                response.raise_for_status()
                vec = cast(list[Any], response.json()["data"][0]["embedding"])
                return [float(x) for x in vec]
        except httpx.TimeoutException as e:
            raise InferenceTimeoutError("llama-server embedding timed out") from e
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"llama-server embeddings error {e.response.status_code}: {e.response.text}"
            ) from e
        except httpx.ConnectError as e:
            raise RuntimeError(
                f"Cannot connect to llama-server (embeddings) at {self._base_url}"
            ) from e

    def dimensions(self) -> int:
        return self.DIMENSIONS

    @property
    def name(self) -> str:
        return "llamacpp-embed"
