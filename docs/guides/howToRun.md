# How to Run Cerebro (llama.cpp + Frontend)

You need **3 terminals**. Run them in this order.

---

## Fix required before first run

The `.args` config files have a bug — fix them once:

```bash
sed -i '' 's/^--flash-attn$/--flash-attn on/' \
  /Users/mb/Desktop/Javier/SecondBrain/cerebro/config/chat.args \
  /Users/mb/Desktop/Javier/SecondBrain/cerebro/config/coding.args \
  /Users/mb/Desktop/Javier/SecondBrain/cerebro/config/deep.args
```

---

## Terminal 1 — llama.cpp engine (start first)

```bash
cd /Users/mb/Desktop/Javier/SecondBrain/cerebro
make engine
```

Wait until you see `llama server listening` before moving on.
Leave this terminal running.

**Profile options** (pick one instead of `make engine`):

| Command | Best for |
|---|---|
| `make engine` | Chat, quick questions (ctx 2048, less RAM) |
| `make engine-code` | Code analysis (ctx 8192 — close Chrome first) |
| `make engine-deep` | Documents, RAG, summaries (ctx 6144) |

---

## Terminal 2 — Cerebro backend

```bash
cd /Users/mb/Desktop/Javier/SecondBrain/cerebro
source .venv/bin/activate
CEREBRO_INFERENCE_BACKEND=llamacpp make run
```

Server starts at `http://localhost:7842`.
Leave this terminal running.

> Ollama must also be running for embeddings: `ollama serve` (if not already running)

---

## Terminal 3 — Frontend

### Option A: Dev mode (browser, hot reload)

```bash
cd /Users/mb/Desktop/Javier/SecondBrain/cerebro/ui/tray
npm run dev
```

### Option B: Desktop app (opens like a real Mac app)

```bash
cd /Users/mb/Desktop/Javier/SecondBrain/cerebro/ui/tray
npx tauri dev
```

This opens Cerebro as a native desktop window (not in the browser). Requires Rust + Tauri CLI installed. If you get a "tauri not found" error, install Rust first:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

Then re-run `npx tauri dev`.

> **Note**: `npx tauri dev` rebuilds the Rust binary on first run — expect 2-5 minutes the first time.

---

## Quick health check

```bash
curl http://localhost:7842/status
```

Look for `"provider": "llamacpp"` in the response.

---

## Troubleshooting

**`make engine` fails with `--flash-attn` error** → Run the fix command above (one time only).

**Cerebro says connection error** → llama-server isn't running yet. Start Terminal 1 first.

**Very slow responses** → Close Chrome, use `make engine` instead of `make engine-code`.

**Mac freezes 2-3 sec when stopping engine** → Normal, macOS releasing RAM.
