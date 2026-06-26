from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any, cast

import httpx
from loguru import logger

from core.inference.context_usage import log_context_usage, resolve_token_usage
from core.inference.engine import InferenceTimeoutError, ModelNotFoundError
from core.inference.ram_preflight import run_ram_preflight
from core.inference.registry import Message

_PROFILE_CTX: dict[str, int] = {
    "chat": 4096,
    "coding": 8192,
    "deep": 6144,
}

_VISION_MODEL_RE = re.compile(
    r"\b(VL|vision|multimodal|mmproj|llava|llama-vision)\b", re.IGNORECASE
)


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
        self._ram_override_ctx: int | None = None
        self.supports_vision: bool = bool(_VISION_MODEL_RE.search(model))

    async def complete(self, messages: list[Message], **kwargs) -> str:
        run_ram_preflight()
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "temperature": kwargs.get("temperature"),
            "grammar": kwargs.get("grammar"),
            "max_tokens": kwargs.get("max_tokens", 2048),
        }
        if "n_ctx" in kwargs:
            payload["n_ctx"] = kwargs["n_ctx"]
        if "cache_prompt" in kwargs:
            payload["cache_prompt"] = kwargs["cache_prompt"]
        # remove None values — llama-server uses its own defaults when omitted
        payload = {k: v for k, v in payload.items() if v is not None}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(f"{self._base_url}/v1/chat/completions", json=payload)
                if response.status_code == 404:
                    raise ModelNotFoundError(f"Model '{self._model}' not found in llama-server")
                response.raise_for_status()
                data = cast(dict[str, Any], response.json())
                tokens_used, source = resolve_token_usage(data, messages)
                log_context_usage(tokens_used, self.context_window(), source)
                msg = data["choices"][0]["message"]
                content: str = (msg.get("content") or msg.get("reasoning_content") or "").strip()
                return content
        except httpx.TimeoutException as e:
            raise InferenceTimeoutError("llama-server chat timed out") from e
        except httpx.ConnectError as e:
            raise LlamaCppUnavailableError(
                f"Cannot connect to llama-server at {self._base_url}"
            ) from e

    async def stream(self, messages: list[Message], **kwargs: Any) -> AsyncIterator[str]:
        run_ram_preflight()
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": True,
            "grammar": kwargs.get("grammar"),
            "max_tokens": kwargs.get("max_tokens", 2048),
        }
        if "n_ctx" in kwargs:
            payload["n_ctx"] = kwargs["n_ctx"]
        if "cache_prompt" in kwargs:
            payload["cache_prompt"] = kwargs["cache_prompt"]
        payload = {k: v for k, v in payload.items() if v is not None}
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
                        if data.get("usage"):
                            tokens_used, source = resolve_token_usage(data, messages)
                            log_context_usage(tokens_used, self.context_window(), source)
        except httpx.ConnectError as e:
            raise LlamaCppUnavailableError(
                f"Cannot connect to llama-server at {self._base_url}"
            ) from e

    def set_model(self, model: str) -> None:
        self._model = model

    def model_id(self) -> str:
        return self._model

    def context_window(self) -> int:
        if self._ram_override_ctx is not None:
            return self._ram_override_ctx
        return _PROFILE_CTX.get(self._profile, 2048)

    def reduce_context(self, factor: float = 0.5) -> None:
        base = _PROFILE_CTX.get(self._profile, 2048)
        self._ram_override_ctx = max(512, int(base * factor))

    def is_available(self) -> bool:
        try:
            with httpx.Client(timeout=httpx.Timeout(2.0)) as client:
                response = client.get(f"{self._base_url}/health")
                return int(response.status_code) == 200
        except Exception:
            logger.debug("llama-server unavailable at {}", self._base_url)
            return False
