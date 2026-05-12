from __future__ import annotations

import asyncio
import queue
import threading
from collections.abc import AsyncIterator

from loguru import logger

from core.inference.registry import Message


class MlxChatProvider:
    """In-process LLM inference via mlx-lm on Apple Silicon.

    All MLX operations (load + generate) run on a single persistent worker
    thread because MLX GPU streams are thread-local: using model weights from
    a different thread than the one that loaded them raises
    "There is no Stream(gpu, ...) in current thread".
    """

    def __init__(self, model_repo: str, max_tokens: int = 2048) -> None:
        self._model_repo = model_repo
        self._max_tokens = max_tokens
        self._model = None
        self._tokenizer = None
        self._ready = threading.Event()
        self._task_queue: queue.SimpleQueue = queue.SimpleQueue()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

    def _worker_loop(self) -> None:
        from mlx_lm import load  # type: ignore[import]

        logger.info("Loading MLX model: {}", self._model_repo)
        self._model, self._tokenizer = load(self._model_repo)
        logger.info("MLX model loaded.")
        self._ready.set()

        while True:
            task = self._task_queue.get()
            if task is None:
                break
            task()

    def _apply_template(self, messages: list[Message]) -> str:
        if hasattr(self._tokenizer, "apply_chat_template"):
            return self._tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        return "\n".join(f"{m['role']}: {m['content']}" for m in messages)

    async def complete(self, messages: list[Message], **kwargs) -> str:
        from mlx_lm import generate  # type: ignore[import]

        await asyncio.to_thread(self._ready.wait)
        prompt = self._apply_template(messages)
        loop = asyncio.get_event_loop()
        fut: asyncio.Future[str] = loop.create_future()

        def _task() -> None:
            try:
                result = generate(
                    self._model,
                    self._tokenizer,
                    prompt=prompt,
                    max_tokens=self._max_tokens,
                    verbose=False,
                )
                loop.call_soon_threadsafe(fut.set_result, result)
            except Exception as exc:
                loop.call_soon_threadsafe(fut.set_exception, exc)

        self._task_queue.put(_task)
        return await fut

    async def stream(self, messages: list[Message]) -> AsyncIterator[str]:
        from mlx_lm import stream_generate  # type: ignore[import]

        await asyncio.to_thread(self._ready.wait)
        prompt = self._apply_template(messages)
        loop = asyncio.get_event_loop()
        token_queue: asyncio.Queue[str | None] = asyncio.Queue()

        def _task() -> None:
            try:
                for response in stream_generate(
                    self._model,
                    self._tokenizer,
                    prompt=prompt,
                    max_tokens=self._max_tokens,
                ):
                    text = response.text if hasattr(response, "text") else response
                    loop.call_soon_threadsafe(token_queue.put_nowait, text)
            finally:
                loop.call_soon_threadsafe(token_queue.put_nowait, None)

        self._task_queue.put(_task)

        while True:
            token = await token_queue.get()
            if token is None:
                break
            yield token

    def model_id(self) -> str:
        return self._model_repo

    def context_window(self) -> int:
        return 4096

    def is_available(self) -> bool:
        from core.inference.platform import mlx_available

        return mlx_available()


class MlxEmbeddingProviderStub:
    """Stub — satisfies ProviderRegistry.register() signature.

    MLX does not provide its own embeddings; LlamaCppEmbeddingProvider is
    passed directly to LongTermStore. This stub exists only so that the MLX
    registry entry can be registered without a real embed implementation.
    """

    async def embed(self, text: str) -> list[float]:  # pragma: no cover
        raise NotImplementedError("Use LlamaCppEmbeddingProvider for embeddings")

    def dimensions(self) -> int:
        return 768
