# Engine / backend split — Fases 0 y 1

> **Estado:** ✅ completadas (2026-06-25)  
> **Plan maestro:** [`docs/plans/engine-backend-split.md`](../plans/engine-backend-split.md)

## Fase 0 — Preparación (sin cambio de comportamiento)

### Cambios

| Área | Archivo | Qué hace |
|------|---------|----------|
| Flag de arranque | `core/feature_flags.py` | `auto_start_engine_enabled()` lee `CEREBRO_AUTO_START_ENGINE` (default `true`) |
| Boot legacy | `main.py` | `_ensure_engine_running()` y el restart tras `chat.args` stale respetan el flag |
| Intención del usuario | `core/inference/engine_desired.py` | Default `off` — motor solo con Start engine o `make dev-full` |
| Health monitor | `core/inference/health_monitor.py` | No reinicia si `engine_desired=off` |
| Tests | `tests/test_engine_desired.py`, `tests/test_feature_flags.py` | Cobertura mock, sin llama.cpp |

### Comportamiento

Con el default actual (`CEREBRO_AUTO_START_ENGINE=true`), `make run` y el launcher siguen levantando el motor como antes. El monitor solo deja de reiniciar cuando `engine_desired=off` (API en Fase 3).

### Verificación

```bash
make test tests/test_engine_desired.py tests/test_health_monitor.py tests/test_feature_flags.py -q
make test-stable
```

---

## Fase 1 — Scripts y Makefile

### Scripts nuevos (`scripts/`)

| Script | Rol |
|--------|-----|
| `cerebro_desktop_common.sh` | Funciones compartidas (config, health, start/stop por puerto) |
| `cerebro_desktop_backend.sh` | Solo backend `:7842` |
| `cerebro_desktop_engine.sh` | Solo motor `:8080` + embed `:8082` (si config) |
| `cerebro_desktop_stop_backend.sh` | Mata `:7842` |
| `cerebro_desktop_stop_engine.sh` | Mata `:8080` y `:8082` |

### Refactor

- `cerebro_desktop_launcher.sh` → `engine.sh` + `backend.sh` (orden legacy: motor primero)
- `cerebro_desktop_stop.sh` → `stop_engine.sh` + `stop_backend.sh`
- Copias sincronizadas vía `ui/tray/src-tauri/build.rs` al empaquetar la app

### Makefile

```bash
make desktop-launch-full   # motor + embed + backend (paridad pre-split)
make desktop-backend       # solo :7842
make desktop-engine        # solo :8080 (+ :8082 si aplica)
make desktop-stop-engine   # solo motor
make desktop-stop-backend  # solo backend
make desktop-stop          # todo
```

`make desktop-launch` es alias de `desktop-launch-full` (compatibilidad).

### Verificación manual

```bash
make desktop-stop
make desktop-backend    # curl -sf http://127.0.0.1:7842/api/health
make desktop-engine     # curl -sf http://127.0.0.1:8080/health
make desktop-launch-full  # equivalente a los dos anteriores juntos
```

---

## Siguiente: Fase 2 ✅ (ver `engine-backend-split-phase2-3.md`)

Completada: default `CEREBRO_AUTO_START_ENGINE=false`, API `/api/engine/*`.
