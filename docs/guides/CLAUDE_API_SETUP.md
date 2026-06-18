# Claude API — Setup & Troubleshooting

## Requirements

- `ANTHROPIC_API_KEY` env var set (via `.env` or environment)
- `CEREBRO_INFERENCE_BACKEND=claude` (default: `llamacpp`)

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-...
CEREBRO_INFERENCE_BACKEND=claude
CEREBRO_CLAUDE_MODEL=claude-sonnet-4-20250514
```

## Quick Start

```bash
make run
# Open http://localhost:7842
```

No inference engine needed — Claude runs entirely server-side.

## Model Selection

Configure via `CEREBRO_CLAUDE_MODEL` (default: `claude-sonnet-4-20250514`).

| Model ID | Context Window | Notes |
|----------|---------------|-------|
| `claude-fable-5` | 1M | Most capable (Anthropic's best) |
| `claude-opus-4-8` | 1M | Maximum reasoning |
| `claude-sonnet-4-6` | 1M | Default — best balance |
| `claude-haiku-4-5` | 200K | Fast/cheap |

## Embeddings

When `CEREBRO_INFERENCE_BACKEND=claude`, embeddings **always default to local** (sentence-transformers `all-MiniLM-L6-v2`, 384d) regardless of available RAM. Override via:

```bash
CEREBRO_EMBEDDINGS_BACKEND=llamacpp   # requires embed server on :8082
```

## Known Limitations

| Limitation | Detail |
|------------|--------|
| Vision/Images | Supported (`supports_vision=True`) but image content blocks in `runtime.py:1508-1514` still use OpenAI `image_url` format. Full Anthropic `image` format requires a conditional branch. |
| Tool calling | Works via JSON prompt engineering (not native Anthropic `tool_use` blocks) |
| Latency | Network-dependent; no local inference overhead |

## Changes Applied (2026-06-17)

### 1. `claude_api_provider.py` — 4 fixes

| # | Line | Before | After | Impact |
|---|------|--------|-------|--------|
| 1 | 66 | `stream(self, messages)` | `stream(self, messages, **kwargs)` | Enables **live streaming** from agent loop. Without this, `_chat_supports_grammar_stream()` returns `False` and the runtime falls back to `complete()`, delivering all tokens at once after full generation. |
| 2 | 11 | `_DEFAULT_MODEL` outdated | `"claude-sonnet-4-6"` | Default is now the latest Sonnet. |
| 3 | 12-17 | Context map outdated | `claude-fable-5` (1M), `opus-4-8` (1M), `sonnet-4-6` (1M), `haiku-4-5` (200K) | Accurate model IDs and context windows. |
| 4 | 24 | `supports_vision = False` | `supports_vision = True` | Claude natively supports images; flag was wrong. |

Additionally, `stream()` now catches `anthropic.AuthenticationError` (line 87-88), matching `complete()`. Previously, an invalid API key would cause an unhandled exception during streaming.

### 2. `main.py` — 2 fixes

| # | Line | Before | After | Impact |
|---|------|--------|-------|--------|
| 5 | 230 | `_ensure_chat_args()` ran unconditionally | Wrapped in `if INFERENCE_BACKEND == "llamacpp":` | Prevents unnecessary `config/chat.args` rewrites and engine restart attempts when using Claude. Eliminates confusing log noise. |
| 6 | 286 | `os.environ.get("CEREBRO_CLAUDE_MODEL", "claude-sonnet-4-6")` | `"claude-sonnet-4-20250514"` | Consistent default with the provider. |

### 3. `embedding_factory.py` — 1 fix

| # | Line | Before | After | Impact |
|---|------|--------|-------|--------|
| 7 | 16-24 | RAM-based auto-select only | Checks `CEREBRO_INFERENCE_BACKEND` first; if `claude`, defaults to `"local"` | On >10GB RAM machines using Claude API, embeddings no longer try to connect to a llama.cpp embed server (`:8082`) that isn't running. |

## Files Modified

```
core/inference/providers/claude_api_provider.py   — 4 fixes
main.py                                           — 2 fixes (guards, default model)
core/inference/embedding_factory.py               — 1 fix (Claude-aware selection)
docs/guides/CLAUDE_API_SETUP.md                   — this file
```

## Verification

```bash
# Syntax check
python -c "import py_compile; py_compile.compile('main.py', doraise=True)"
python -c "import py_compile; py_compile.compile('core/inference/providers/claude_api_provider.py', doraise=True)"
python -c "import py_compile; py_compile.compile('core/inference/embedding_factory.py', doraise=True)"

# Tests (all pass)
python -m pytest tests/ -k "claude" -v
python -m pytest tests/ -k "embed" -v
make test-stable
```

## Unresolved Issues

| Issue | File | Impact |
|-------|------|--------|
| Image content blocks use OpenAI format | `runtime.py:1508-1514` | Image attachments won't render correctly with Claude. Needs Anthropic `image` content block format. |
| `[claude]` section in `settings.toml` is dead code | `config/settings.toml:76-79` | Editing it has no effect. All Claude config is via env vars. |
