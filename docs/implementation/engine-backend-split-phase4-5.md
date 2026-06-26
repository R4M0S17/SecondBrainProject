# Engine / backend split — Fases 4 y 5

> **Estado:** ✅ completadas (2026-06-25)  
> **Plan maestro:** [`docs/plans/engine-backend-split.md`](../plans/engine-backend-split.md)

## Fase 4 — Frontend + Tauri

### Tauri (`ui/tray/src-tauri/`)

| Cambio | Detalle |
|--------|---------|
| `setup` | `ensure_backend_on_startup()` en background al abrir la app |
| Commands nuevos | `start_cerebro_backend`, `start_cerebro_engine` |
| Proxy API | Timeout 200s para `POST /api/engine/start` |
| Legacy | `restart_cerebro_services` / `stop_cerebro_services` siguen disponibles |

### Store `services.ts`

| Antes | Ahora |
|-------|-------|
| `servicesOff` | `backendReady` + `engineDesired` |
| Turn On → launcher full | Turn On → `POST /api/engine/start` (fallback script engine) |
| Turn Off → stop todo | Turn Off → `POST /api/engine/stop` (backend sigue) |

`probeBackend()`: health check → si falla en Tauri, `start_cerebro_backend`.

### UI

- **ServiceControls:** solo visible con backend `llamacpp`; oculto para Claude/MLX
- **EngineIndicator:** rojo = backend offline; gris = motor apagado; verde = motor OK
- **InputArea:** deshabilitado solo si `!backendReady`; fast paths permitidos con motor off
- **i18n:** `Start engine` / `Encender motor`, `status.backend_offline`, placeholders actualizados

### API client

`getEngineStatus()`, `startEngine()`, `stopEngine()` en `api/client.ts`.

### Tests frontend

- `EngineIndicator.test.tsx` (backend offline, engine off, Claude)
- `StatusBar.test.tsx` actualizado al nuevo store

---

## Fase 5 — Consolidación y docs

| Documento | Cambio |
|-----------|--------|
| `docs/guides/DESKTOP_ONE_CLICK_LAUNCH.md` | Flujo split backend/motor |
| `AGENTS.md` | Comandos y API engine |
| `README.md` | Quick start: `make run` + `make engine` / Turn On en app |
| `docs/reference/changes.md` | Entrada Fases 4–5 |
| `docs/plans/CURRENT_FOCUS.md` | Tarea completada |
| `docs/plans/engine-backend-split.md` | Plan cerrado (Fases 0–5 ✅) |

### Legacy

- `CEREBRO_AUTO_START_ENGINE=true` → opt-in vía `make dev-full`
- `make desktop-launch-full` → motor + backend (escape hatch)

---

## Flujo usuario (desktop, lite-8gb)

1. Abrir **Cerebro.app** → backend arranca en background (~30 s)
2. Settings / documentos / historial **funcionan** sin motor
3. **Start engine** → `POST /api/engine/start` → chat LLM
4. **Stop engine** → motor off; backend y settings siguen
5. Cerrar app → backend puede seguir (recomendado en 8 GB)

## Verificación

```bash
make test-stable
make test tests/test_engine_api.py -q
cd ui/tray && npm run test -- --run src/components/status/
```
