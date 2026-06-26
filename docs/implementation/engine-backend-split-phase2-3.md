# Engine / backend split — Fases 2 y 3

> **Estado:** ✅ completadas (2026-06-25)  
> **Plan maestro:** [`docs/plans/engine-backend-split.md`](../plans/engine-backend-split.md)  
> **Fases previas:** [`engine-backend-split-phase0-1.md`](engine-backend-split-phase0-1.md)

## Fase 2 — Backend sin auto-arranque de motor

### Cambios

| Área | Archivo | Qué hace |
|------|---------|----------|
| Default del flag | `core/feature_flags.py` | `CEREBRO_AUTO_START_ENGINE` default → `false` |
| Perfil lite | `config/profiles/lite-8gb.env` | `CEREBRO_AUTO_START_ENGINE=false` explícito |
| Boot | `main.py` | `_ensure_engine_running()` ya respetaba el flag; `EngineSuspender` solo si hay PID en `:8080` |
| Dev legacy | `Makefile` | `make dev-full` = `CEREBRO_AUTO_START_ENGINE=true make run` |

### Comportamiento nuevo

```bash
make run          # :7842 up, :8080 down (sin GGUF cargado)
make engine       # :8080 up cuando quieras chatear
make dev-full     # paridad antigua: backend + auto-start motor
make lite         # perfil 8 GB: backend solo + embed local
```

`_ensure_chat_args()` **sigue** reescribiendo `config/chat.args` al arrancar el backend (modelo correcto para cuando enciendas el motor).

### Verificación

```bash
make test tests/test_feature_flags.py -q
curl -s http://127.0.0.1:7842/api/status | jq .engine_ok   # false sin motor
make engine
curl -s http://127.0.0.1:7842/api/status | jq .engine_ok   # true
```

---

## Fase 3 — API de motor + health monitor

### Módulo `core/inference/engine_manager.py`

| Función | Rol |
|---------|-----|
| `spawn_chat_engine` / `spawn_embed_engine` | Arranque vía `bin/start_engine.sh` |
| `stop_all_engines` | Mata `:8080` y `:8082` |
| `wait_for_chat` / `wait_for_embed` | Health poll (180s / 60s) |
| `start_engine_sync` | `engine_desired=on` + spawn + wait |
| `stop_engine_sync` | `engine_desired=off` + stop ports |
| `get_status` | Estado agregado para la API |

Embed `:8082` solo se arranca si `default_embeddings_backend() == "llamacpp"` (en lite-8gb, local → skip).

### Endpoints REST (`ui/tray/server.py`)

| Método | Ruta | Respuesta |
|--------|------|-----------|
| `GET` | `/api/engine/status` | `{ desired, running, model, llama_server, embed_running }` |
| `POST` | `/api/engine/start` | Enciende motor; 503 si no healthy; 400 si backend ≠ llamacpp |
| `POST` | `/api/engine/stop` | Apaga motor; `engine_desired=off`; health monitor no reinicia |

Tras `POST /api/engine/start`, se re-enlaza `EngineSuspender` si hay PID en `:8080`.

### Health monitor

Ya consultaba `engine_desired` (Fase 0). `_default_spawn_engine` delega en `engine_manager.spawn_chat_engine`.

### Tests

`tests/test_engine_api.py` — status, start, stop, 503/400, y que el monitor **no** reinicia tras `POST /api/engine/stop`.

### Uso programático

```bash
curl -s http://127.0.0.1:7842/api/engine/status | jq
curl -X POST http://127.0.0.1:7842/api/engine/start
curl -X POST http://127.0.0.1:7842/api/engine/stop
```

---

## Siguiente: Fase 4

- Tauri: `ensure_backend` al abrir app
- Frontend: Turn On/Off → `POST /api/engine/start|stop` (no launcher completo)
- `services.ts`: `backendReady` vs `engineOk`
