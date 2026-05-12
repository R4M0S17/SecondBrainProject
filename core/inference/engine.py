from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx
from loguru import logger


class InferenceTimeoutError(Exception):
    pass


class ModelNotFoundError(Exception):
    pass


class LlamaCppUnavailableError(Exception):
    pass


class InferenceEngine:
    EMBEDDING_MODEL = "nomic-embed-text"

    def __init__(self, model: str, base_url: str = "http://127.0.0.1:8080") -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(30.0)

    async def complete(self, prompt: str, system: str = "") -> str:
        payload: dict = {"model": self.model, "prompt": prompt, "stream": False}
        if system:
            payload["system"] = system

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(f"{self.base_url}/api/generate", json=payload)
                if response.status_code == 404:
                    raise ModelNotFoundError(f"Model '{self.model}' not found")
                response.raise_for_status()
                return response.json()["response"].strip()
        except httpx.TimeoutException as e:
            raise InferenceTimeoutError("llama.cpp timed out after 30s") from e
        except httpx.ConnectError as e:
            raise LlamaCppUnavailableError(f"Cannot connect to llama.cpp at {self.base_url}") from e

    async def embed(self, text: str) -> list[float]:
        payload = {"model": self.EMBEDDING_MODEL, "prompt": text}

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(f"{self.base_url}/api/embeddings", json=payload)
                if response.status_code == 404:
                    raise ModelNotFoundError(f"Embedding model '{self.EMBEDDING_MODEL}' not found")
                response.raise_for_status()
                return response.json()["embedding"]
        except httpx.TimeoutException as e:
            raise InferenceTimeoutError("Embedding timed out after 30s") from e
        except httpx.ConnectError as e:
            raise LlamaCppUnavailableError(f"Cannot connect to llama.cpp at {self.base_url}") from e

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        payload = {"model": self.model, "prompt": prompt, "stream": True}

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(None)) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/api/generate", json=payload
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        data = json.loads(line)
                        if token := data.get("response"):
                            yield token
                        if data.get("done"):
                            break
        except httpx.ConnectError as e:
            raise LlamaCppUnavailableError(f"Cannot connect to llama.cpp at {self.base_url}") from e

    def is_available(self) -> bool:
        try:
            with httpx.Client(timeout=httpx.Timeout(5.0)) as client:
                response = client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            logger.debug("llama.cpp unavailable at {}", self.base_url)
            return False
