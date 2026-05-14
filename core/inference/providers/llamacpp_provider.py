from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, cast

import httpx
from loguru import logger

from core.inference.engine import InferenceTimeoutError, ModelNotFoundError
from core.inference.registry import Message

_PROFILE_CTX: dict[str, int] = {
    "chat": 2048,
    "coding": 8192,
    "deep": 6144,
}


class LlamaCppUnavailableError(Exception):
    pass


class LlamaCppChatProvider:
    def __init__(
        self,
        model: str,
        base_url: str = "http://127.0.0.1:8080",
        profile: str = "chat",
        timeout: int = 60,
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._profile = profile
        self._timeout = httpx.Timeout(float(timeout))

    async def complete(self, messages: list[Message], **kwargs) -> str:
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "temperature": kwargs.get("temperature"),
        }
        # remove None values — llama-server uses its own defaults when omitted
        payload = {k: v for k, v in payload.items() if v is not None}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(f"{self._base_url}/v1/chat/completions", json=payload)
                if response.status_code == 404:
                    raise ModelNotFoundError(f"Model '{self._model}' not found in llama-server")
                response.raise_for_status()
                data = cast(dict[str, Any], response.json())
                return str(data["choices"][0]["message"]["content"]).strip()
        except httpx.TimeoutException as e:
            raise InferenceTimeoutError("llama-server chat timed out") from e
        except httpx.ConnectError as e:
            raise LlamaCppUnavailableError(
                f"Cannot connect to llama-server at {self._base_url}"
            ) from e

    async def stream(self, messages: list[Message]) -> AsyncIterator[str]:
        payload = {"model": self._model, "messages": messages, "stream": True}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(None)) as client:
                async with client.stream(
                    "POST", f"{self._base_url}/v1/chat/completions", json=payload
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        raw = line[len("data: ") :]
                        if raw.strip() == "[DONE]":
                            break
                        data = json.loads(raw)
                        if token := data.get("choices", [{}])[0].get("delta", {}).get("content"):
                            yield token
        except httpx.ConnectError as e:
            raise LlamaCppUnavailableError(
                f"Cannot connect to llama-server at {self._base_url}"
            ) from e

    def set_model(self, model: str) -> None:
        self._model = model

    def model_id(self) -> str:
        return self._model

    def context_window(self) -> int:
        return _PROFILE_CTX.get(self._profile, 2048)

    def is_available(self) -> bool:
        try:
            with httpx.Client(timeout=httpx.Timeout(2.0)) as client:
                response = client.get(f"{self._base_url}/health")
                return int(response.status_code) == 200
        except Exception:
            logger.debug("llama-server unavailable at {}", self._base_url)
            return False
