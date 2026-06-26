# How to Run Cerebro

Spanish version: [`running-es.md`](running-es.md).

> **TL;DR (development):** `npm run tauri:dev` → backend starts automatically, **LLM stays off** until you click **Start engine** in the header.

---

## First-time setup (once)

```bash
cd /Users/mb/Desktop/Javier/SecondBrain
make install
make desktop-config    # writes ~/.cerebro/desktop.json (needed for Tauri + desktop scripts)
```

---

## Recommended — Tauri dev (UI hot-reload, LLM on demand)

Best when you edit React/UI code and want the native window.

### One terminal

```bash
cd /Users/mb/Desktop/Javier/SecondBrain/ui/tray
npm run tauri:dev
```

**What happens:**

| Step | Behavior |
|------|----------|
| App opens | Tauri window (native shell) |
| Backend `:7842` | Auto-starts in background if not running |
| LLM `:8080` | **Does not** start — waits for **Start engine** |
| UI changes | Hot-reload on save |

Use **Start engine** / **Stop engine** in the header (top bar) to control the llama-server.

With the engine **off**, you can still use: Settings, documents, history, and fast paths (math, calendar read, file search, etc.).

### Optional: explicit backend in a second terminal

If you prefer to see backend logs in a terminal:

```bash
# Terminal 1
cd /Users/mb/Desktop/Javier/SecondBrain
make lite          # 8 GB Mac — recommended
# or: make run

# Terminal 2
cd /Users/mb/Desktop/Javier/SecondBrain/ui/tray
npm run tauri:dev
```

---

## Packaged app (Dock / Applications)

```bash
cd /Users/mb/Desktop/Javier/SecondBrain
make desktop-app && make desktop-install
open /Applications/Cerebro.app
```

| Action | Result |
|--------|--------|
| Open app | Backend `:7842` auto-starts |
| **Start engine** | LLM `:8080` only |
| **Stop engine** | Frees ~2 GB RAM; backend stays up |
| Code changes | **Not** auto-applied — rebuild with `make desktop-app && make desktop-install` |

Daily open after install:

```bash
open /Applications/Cerebro.app
```

---

## Other run modes

### Legacy — everything in one terminal (backend + LLM auto)

```bash
cd /Users/mb/Desktop/Javier/SecondBrain
make dev-full
```

Same as pre-split behavior: loads the GGUF on boot (~2.5 GB RAM).

### Classic dev — 3 terminals (manual control)

```bash
# Terminal 1 — backend only
make lite    # or make run

# Terminal 2 — LLM (only when you need chat)
make engine

# Terminal 3 — browser UI (no Tauri shell)
cd ui/tray && npm run dev
```

### Desktop scripts (no npm)

```bash
make desktop-backend    # API :7842 only
make desktop-engine     # llama-server :8080 only
make desktop-launch-full # both (legacy one-click)
make desktop-stop       # stop everything
make desktop-stop-engine   # stop LLM only
```

---

## Engine control (API)

```bash
curl -s http://127.0.0.1:7842/api/engine/status | jq
curl -X POST http://127.0.0.1:7842/api/engine/start
curl -X POST http://127.0.0.1:7842/api/engine/stop
```

---

## Health check

```bash
curl -s http://127.0.0.1:7842/api/health
curl -s http://127.0.0.1:7842/api/status | jq .engine_ok
```

- `engine_ok: false` → backend up, LLM off (expected before **Start engine**)
- `engine_ok: true` → LLM ready for chat

---

## Troubleshooting

### LLM starts by itself after ~10–30 seconds

The health monitor only auto-restarts the engine when `engine_desired` is `"on"`. By default it is **`off`** until you press **Start engine**.

If it still auto-starts:

```bash
# 1. Stop the engine
make desktop-stop-engine

# 2. Clear stale "desired: on" state (from a previous session)
rm -f ~/.cerebro/state/engine.json

# 3. Restart backend (close make run / make lite, or:)
make desktop-stop-backend

# 4. Relaunch Tauri
cd ui/tray && npm run tauri:dev
```

Do **not** use `make dev-full` or `make desktop-launch-full` if you want button-only engine control.

### Start engine button disabled

Backend is down. Wait for auto-start or run `make lite` in a terminal.

### Chat works for math/calendar but not open-ended questions

Engine is off — click **Start engine** and wait 15–90 s (model load).

### Other issues

| Symptom | Fix |
|---------|-----|
| `make desktop-app` fails | Run `make desktop-config`; check `~/.cerebro/desktop.json` |
| Settings don't load | Backend down — `make run` or `make desktop-backend` |
| Port in use | `make desktop-stop` then retry |
| `--flash-attn` error | `sed -i '' 's/^--flash-attn$/--flash-attn on/' config/chat.args config/coding.args config/deep.args` |
| Mac freezes 2–3s on Stop engine | Normal — macOS freeing ~2.5 GB RAM |

---

## Related docs

- [`DESKTOP_ONE_CLICK_LAUNCH.md`](DESKTOP_ONE_CLICK_LAUNCH.md) — build `.app`, Dock, packaging
- [`8gb-mac-quickstart.md`](8gb-mac-quickstart.md) — RAM profile
- [`engine-backend-split-phase4-5.md`](../implementation/engine-backend-split-phase4-5.md) — architecture notes
