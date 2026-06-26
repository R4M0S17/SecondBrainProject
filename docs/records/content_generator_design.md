# File Content Generator Design (ADR)

**Date**: 2026-06-23
**Status**: Active
**Deciders**: Architecture team

## Context

The `generate_file_content` function in `core/agents/file_content_generator.py` is
responsible for producing the body text when a user asks to create a file with a
description instead of literal content (e.g. "crea un archivo con 4 nombres de mujer"
→ the body `"Lucía\nSofía\nValentina\nMía"` must be generated).

Two mechanisms exist:

1. **Heuristic fallback** — regex‑based pattern matching that returns hardcoded
   content without calling the LLM. Fast (~0ms).
2. **LLM generation** — calls the configured chat provider (llamacpp, MLX, Claude)
   with a focused prompt. Slow (10–90s depending on provider and content).

## Problem

The original implementation wrapped the LLM call in `asyncio.wait_for` with a
25 s timeout. When the LLM took longer (common on 8 GB M1 with Qwen3.5‑2B for
recipes, code, or longer lists), the timeout killed the fast‑path, which then
fell through to the LangGraph agent loop. The agent loop runs the LLM with the
full system prompt (tools, history, etc.) and no timeout, producing worse
content (sometimes JSON envelopes) in 2–3× the time.

Additionally, the heuristic fallback covered only a few patterns (female/male
names, pizza recipe, PlayStation games). Any query outside those patterns was
forced through the LLM path with the 25 s timeout, creating a reliability cliff.

## Decision

1. **Remove the artificial timeout** (`asyncio.wait_for`) from the LLM call in
   `generate_file_content`. The provider's own HTTP timeout (60 s for llamacpp,
   configurable per provider) is the only bound.

2. **Keep the heuristic fallback as an optimisation**, not a requirement. If a
   pattern matches, content is returned instantly. If not, the LLM handles it
   with no extra restrictions.

3. **Document this design** so future contributors understand that the fallback
   is a speed cache, NOT a hard requirement for correctness.

## Consequences

- **Positive**: The LLM can now generate ANY content — recipes, prime numbers,
  country lists, PS5 games, code — without risking a fast‑path timeout and
  fallback to the slower LangGraph loop.
- **Positive**: The fast path succeeds for all file‑create queries, not just
  those matching a hardcoded pattern. Response time is bounded by the provider,
  not an arbitrary constant.
- **Positive**: Removing the timeout removes one failure mode (TimeoutError →
  ValueError → caught → fast path returns None).
- **Negative**: Queries that do not match a fallback pattern will wait for the
  full LLM generation time (~40–90 s) before the file is created. This is the
  same behaviour the system had before the 25 s timeout was introduced.

## Fallback pattern guidelines

Add new patterns to `_FALLBACK_PATTERNS` in `file_content_generator.py` when:

- The query type is extremely common and predictable (e.g. common recipes,
  name lists, console game lists).
- The output is small and unambiguous.
- The pattern reduces observed P95 latency for real users.

Do NOT add patterns for:

- Anything that requires creativity or variation (let the LLM handle it).
- Niche queries that users ask once.

## Related files

- `core/agents/file_content_generator.py` — implementation
- `tests/test_file_write_fast_path.py` — tests for fallback + LLM path
- `tests/fixtures/stable_fast_path_prompts.yaml` — integration fixtures
