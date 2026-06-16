from __future__ import annotations

import asyncio
import queue
import re
import threading
from collections.abc import AsyncIterator

from loguru import logger

from core.inference.registry import Message

_VLM_MODEL_RE = re.compile(
    r"\b(VL|vlm|vision|Qwen3\.5|Qwen2\.5-VL|Qwen2-VL|Llama-Vision|Phi-4-vision|PaliGemma|Florence)\b",
    re.IGNORECASE,
)

_MODEL_LOAD_TIMEOUT = 120.0


class MlxLoadError(RuntimeError):
    pass


class MlxChatProvider:
    def __init__(self, model_repo: str, max_tokens: int = 2048) -> None:
        self._model_repo = model_repo
        self._max_tokens = max_tokens
        self._is_vlm = bool(_VLM_MODEL_RE.search(model_repo))
        self._model = None
        self._tokenizer = None
        self._processor = None
        self._ready = threading.Event()
        self._load_error: Exception | None = None
        self._task_queue: queue.SimpleQueue = queue.SimpleQueue()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()
        self.supports_vision = self._is_vlm

    def _worker_loop(self) -> None:
        try:
            if self._is_vlm:
                from mlx_vlm import load as vlm_load

                logger.info("Loading MLX VLM model: {}", self._model_repo)
                self._model, self._processor = vlm_load(self._model_repo)
                self._tokenizer = self._processor.tokenizer
                logger.info("MLX VLM model loaded ({}).", self._model_repo)
            else:
                from mlx_lm import load as lm_load

                logger.info("Loading MLX text model: {}", self._model_repo)
                self._model, self._tokenizer = lm_load(self._model_repo)
                logger.info("MLX text model loaded ({}).", self._model_repo)
        except Exception as exc:
            logger.error("MLX model load FAILED for {}: {}", self._model_repo, exc)
            self._load_error = exc
        finally:
            self._ready.set()

        while True:
            task = self._task_queue.get()
            if task is None:
                break
            try:
                task()
            except Exception as exc:
                logger.warning("MLX task error: {}", exc)

    def _ensure_loaded(self) -> None:
        if not self._ready.wait(timeout=_MODEL_LOAD_TIMEOUT):
            raise MlxLoadError(
                f"MLX model '{self._model_repo}' did not load within {_MODEL_LOAD_TIMEOUT}s"
            )
        if self._load_error is not None:
            raise MlxLoadError(
                f"MLX model '{self._model_repo}' failed to load: {self._load_error}"
            ) from self._load_error

    def _apply_template(self, messages: list[Message]) -> str:
        tok = self._tokenizer
        if tok is not None and hasattr(tok, "apply_chat_template"):
            return tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        return "\n".join(f"{m['role']}: {m['content']}" for m in messages)

    async def complete(self, messages: list[Message], **kwargs) -> str:
        await asyncio.to_thread(self._ensure_loaded)
        prompt = self._apply_template(messages)
        loop = asyncio.get_event_loop()
        fut: asyncio.Future[str] = loop.create_future()

        def _task() -> None:
            try:
                if self._is_vlm:
                    from mlx_vlm import generate as vlm_generate

                    result = vlm_generate(
                        self._model,
                        self._processor,
                        prompt=prompt,
                        max_tokens=self._max_tokens,
                        verbose=False,
                        temp=0.0,
                    )
                    text = result.text if hasattr(result, "text") else str(result)
                else:
                    from mlx_lm import generate as lm_generate

                    text = lm_generate(
                        self._model,
                        self._tokenizer,
                        prompt=prompt,
                        max_tokens=self._max_tokens,
                        verbose=False,
                        temp=0.0,
                    )
                loop.call_soon_threadsafe(fut.set_result, text)
            except Exception as exc:
                loop.call_soon_threadsafe(fut.set_exception, exc)

        self._task_queue.put(_task)
        return str(await fut)

    async def stream(self, messages: list[Message], **kwargs) -> AsyncIterator[str]:
        await asyncio.to_thread(self._ensure_loaded)
        prompt = self._apply_template(messages)
        loop = asyncio.get_event_loop()
        token_queue: asyncio.Queue[str | None] = asyncio.Queue()
        stall_timeout = 60.0
        first_token_timeout = 30.0

        def _task() -> None:
            try:
                if self._is_vlm:
                    from mlx_vlm import stream_generate as vlm_stream

                    for response in vlm_stream(
                        self._model,
                        self._processor,
                        prompt=prompt,
                        max_tokens=self._max_tokens,
                        temp=0.0,
                    ):
                        text = response.text if hasattr(response, "text") else str(response)
                        if text:
                            loop.call_soon_threadsafe(token_queue.put_nowait, text)
                else:
                    from mlx_lm import stream_generate as lm_stream

                    for response in lm_stream(
                        self._model,
                        self._tokenizer,
                        prompt=prompt,
                        max_tokens=self._max_tokens,
                        temp=0.0,
                    ):
                        text = response.text if hasattr(response, "text") else str(response)
                        if text:
                            loop.call_soon_threadsafe(token_queue.put_nowait, text)
            except Exception as exc:
                logger.warning("MLX stream error: {}", exc)
            finally:
                loop.call_soon_threadsafe(token_queue.put_nowait, None)

        self._task_queue.put(_task)

        got_first = False
        while True:
            try:
                timeout = first_token_timeout if not got_first else stall_timeout
                token = await asyncio.wait_for(token_queue.get(), timeout=timeout)
                if token is None:
                    break
                got_first = True
                yield token
            except TimeoutError:
                logger.warning(
                    "MLX stream stalled ({}s without token)",
                    timeout if got_first else first_token_timeout,
                )
                break

    def model_id(self) -> str:
        return self._model_repo

    def context_window(self) -> int:
        try:
            import json

            from huggingface_hub import hf_hub_download

            config_path = hf_hub_download(self._model_repo, "config.json")
            with open(config_path) as f:
                cfg = json.load(f)
            text_cfg = cfg.get("text_config", {})
            ctx = text_cfg.get("max_position_embeddings") or cfg.get(
                "max_position_embeddings", 4096
            )
            return ctx
        except Exception:
            return 4096

    def is_available(self) -> bool:
        from core.inference.platform import mlx_available

        return mlx_available()

    def reduce_context(self, factor: float = 0.5) -> None:
        self._max_tokens = max(256, int(self._max_tokens * factor))


class MlxEmbeddingProviderStub:
    async def embed(self, text: str) -> list[float]:
        raise NotImplementedError("Use LlamaCppEmbeddingProvider for embeddings")

    def dimensions(self) -> int:
        return 768
