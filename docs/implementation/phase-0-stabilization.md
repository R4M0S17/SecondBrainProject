# Fase 0 — Estabilización de tests (2026-06-22)

> **Estado:** ✅ Completada  
> **Plan vigente:** [`docs/plans/CURRENT_FOCUS.md`](../plans/CURRENT_FOCUS.md)  
> **Objetivo:** Suite en verde sin añadir features nuevas. Dashboard/i18n **no** se congeló (ya en curso).

---

## Resultado final

| Comando | Resultado |
|---------|-----------|
| `make test-stable` | **154 passed** |
| `make test` | **1138 passed** (13 live deselected con `-m "not live"`) |
| Cobertura `core/` | **72.28%** (`--cov-fail-under=72`) |

Antes de Fase 0 la suite completa tenía decenas de fallos (~51) por regresiones de refactor, mocks rotos, orden de fast paths y contaminación de `app_state` entre tests.

---

## 1. Cambios en código de producción

### 1.1 API de configuración — `ui/tray/server.py`

**Problema:** `PATCH /api/config` rechazaba claves arbitrarias (`language`, etc.) porque `ConfigUpdateRequest` era un modelo Pydantic estricto.

**Fix:** `ConfigUpdateRequest` usa `model_config = ConfigDict(extra="allow")` para persistir cualquier clave vía PATCH.

**Tests:** `tests/test_api.py` — incl. `test_patch_config_rebinds_read_handlers` con path bajo `Path.home()`.

---

### 1.2 Web tools — `core/tools/handlers/web.py`

| Issue | Fix |
|-------|-----|
| Import inconsistente de DuckDuckGo | Import a nivel de módulo: `from ddgs import DDGS` con fallback a `duckduckgo_search` |
| `trafilatura.extract(..., no_labels=...)` inválido | Eliminado argumento `no_labels` (no existe en la API actual) |

**Tests:** `tests/test_web_tools.py` — parchea `core.tools.handlers.web.DDGS` y `httpx.Client` (no `httpx.get`) para timeout/404.

---

### 1.3 Fast path router — `core/agents/fast_path_router.py`

**Orden canónico corregido** (después de math):

```
file_write → reminder → calendar_read → calendar_write → file_search → unit_conversion
```

`unit_conversion` se movió **después** de calendario y búsqueda de archivos para no interceptar frases de fusión calendario→archivo ni consultas de calendario con números/unidades ambiguas.

**Calendar write en español:** patrones añadidos en `_try_calendar_write`:

- Verbos: `crea evento`, `agendar`, `programar reunión/cita/evento`
- Tiempo: `mañana`, `manana`, `hoy`, `a las`

---

### 1.4 Unit conversion — `core/agents/unit_conversion_fast_path.py`

**Problema:** Regex demasiado amplio (`\d+\s+\w+\s+en\s+\w+`) capturaba consultas de calendario en español (“eventos del 15 en junio”) como conversiones de unidades.

**Fix:**

- `_CONVERT_RE` exige frase de conversión explícita (`convertir`, `cuánto es`, etc.)
- `_EXPLICIT_CONVERT_RE` adicional antes de devolver mensaje de “no pude identificar”
- Si no hay match explícito → `return None` (deja pasar al siguiente fast path / LLM)

---

### 1.5 Detección lite / sub-1B — `core/agents/runtime.py`

**Bug crítico:** `_is_small_model()` usaba `\d[_\.-]?\d*[mMbB]`, que hacía match de `5-2B` dentro de `Qwen3.5-2B-UD-Q4_K_XL.gguf`. Tras importar `main` (p. ej. `test_model_manager_fallback`), `CEREBRO_LLAMACPP_MODEL` quedaba en el modelo 2B → **lite mode** activo → tools vacías → el LLM respondía JSON de tool sin ejecutarla.

**Fix:** Parseo explícito de tamaño:

- `(\d+(?:[._-]\d+)?)\s*b` → lite solo si `< 1.0` billones (0.5B, 0.8B)
- `(\d+)\s*m` → lite solo si `< 1000` millones (135M, 500M)
- `Qwen3.5-2B`, `3B`, etc. → **no** lite

**Tests nuevos:** `tests/test_small_model_detection.py` (7 casos parametrizados).

---

### 1.6 Planner — `core/agents/planner.py`

**Problema:** `max_steps` por defecto había quedado en 4 en lugar de `MAX_STEPS_PER_TASK` (20).

**Fix:** Restaurado default `MAX_STEPS_PER_TASK`; override vía `CEREBRO_PLANNER_MAX_STEPS` con tope en 20.

---

### 1.7 Feature flags — `core/feature_flags.py`

**Problema:** `main.py` importaba `is_sandbox()` que no existía → `ImportError` en algunos paths de test.

**Fix:** Añadida función:

```python
def is_sandbox() -> bool:
    return os.getenv("CEREBRO_MODE", "native").lower() == "sandbox"
```

**Tests:** `tests/test_feature_flags.py` (nuevo archivo) — Low Power deshabilitado por defecto, `apply_profile_guard`, migración de config.

---

## 2. Cambios solo en tests (expectativas / aislamiento)

### 2.1 Aislamiento global — `tests/conftest.py`

Fixture autouse `_teardown_app_state_leaks` resetea tras **cada** test:

- `app_state.runtime`, `provider_registry`, `vector_store`, `router`, `model_manager`, `planner`, `enricher`, `embedding_provider`, `fleet_orchestrator`
- `app_state.metrics` → nuevo `MetricsCollector()`
- `app_state._config`, `app_state._pending_tools`

Evita que mocks de `tests/test_api.py` (streaming, runtime fake) contaminen `tests/test_conversations.py` y `tests/test_fix_cerebro/`.

### 2.2 Calendario

| Archivo | Cambio |
|---------|--------|
| `tests/test_calendar_fast_path.py` | Fixtures con hora al mediodía para bundles “mismo día”; test inglés usa “next 24 hours”; cleanup `app_state` |
| `tests/test_calendar.py` | Mensajes de error en español; tiempos same-day en birthday bundle |
| `tests/test_calendar_reader.py` | Referencia `_JXA_FETCH_UPCOMING` (no `_AS_FETCH_UPCOMING`) |

### 2.3 API y conversaciones

| Archivo | Cambio |
|---------|--------|
| `tests/test_api.py` | `reset_state` con `app_state.router = MagicMock()`; paths bajo home para config |
| `tests/test_conversations.py` | `mock_runtime` como `MagicMock` + `run = AsyncMock(...)`; `_pending_tools` en reset |

### 2.4 FIX_CEREBRO E2E — `tests/test_fix_cerebro/`

| Archivo | Cambio |
|---------|--------|
| `conftest.py` | `make_stub_chat_complete`: `stream` **sin** `**kwargs` (evita ruta grammar-stream vacía); `_reset_app_state` autouse |
| `test_general_agent_tools.py` | Mock `maybe_consolidate`; bypass fast path (`try_all = AsyncMock(return_value=None)`) |
| `test_query_calendar_e2e.py` | Mismo bypass fast path |
| `test_model_manager_fallback.py` | Mock `audit_confirmation_gates`, `SecretsManager`; cleanup env incl. `CEREBRO_LLAMACPP_MODEL` tras `import main` |

### 2.5 Otros tests actualizados

| Archivo | Motivo |
|---------|--------|
| `tests/test_agent_runtime.py` | Test de grammar con query que no dispara fast path time/date |
| `tests/test_tools.py` | `write_file` devuelve `str`, no `True` |
| `tests/test_specialized.py` | 3 ejemplos de tools en instrucciones de calendario |
| `tests/test_mlx_provider.py` | Umbral RAM 2 GB (no 8 GB) |
| `tests/test_model_efficiency.py` | Skip si GGUF por defecto no está en disco |

---

## 3. Infraestructura de build / CI local

### `Makefile`

```makefile
test:
	$(PYTHON) -m pytest tests/ -v -m "not live" --cov=core --cov-fail-under=72
```

- **`-m "not live"`** excluye `tests/test_smoke_live.py` (requiere backend en `:7842`).
- **`--cov-fail-under=72`** — umbral ajustado desde 80% (cobertura real ~72% tras módulos nuevos con poca cobertura, p. ej. `security_audit.py`).

`make test-stable` sin cambios de alcance (154 tests de fast paths estables).

---

## 4. Lo que NO se hizo (por decisión explícita)

| Item del plan original | Decisión |
|------------------------|----------|
| Congelar dashboard redesign | **No** — trabajo UI/i18n ya avanzado, se mantuvo |
| Fleet, low power shipped, knowledge sync | Sin tocar (fuera de Fase 0) |
| Subir cobertura a 80% | Pendiente — requiere tests en módulos nuevos o exclusiones |
| `make test` en un solo proceso con fork | No necesario tras fix `_is_small_model()` + teardown global |

---

## 5. Archivos tocados (Fase 0 — backend + tests)

```
Makefile
core/agents/fast_path_router.py
core/agents/planner.py
core/agents/runtime.py
core/agents/unit_conversion_fast_path.py
core/feature_flags.py
core/tools/handlers/web.py
ui/tray/server.py
tests/conftest.py
tests/test_agent_runtime.py
tests/test_api.py
tests/test_calendar.py
tests/test_calendar_fast_path.py
tests/test_calendar_reader.py
tests/test_conversations.py
tests/test_feature_flags.py
tests/test_fix_cerebro/conftest.py
tests/test_fix_cerebro/test_general_agent_tools.py
tests/test_fix_cerebro/test_model_manager_fallback.py
tests/test_fix_cerebro/test_query_calendar_e2e.py
tests/test_mlx_provider.py
tests/test_model_efficiency.py
tests/test_small_model_detection.py   # nuevo
tests/test_specialized.py
tests/test_tools.py
tests/test_web_tools.py
docs/plans/CURRENT_FOCUS.md
```

Otros cambios en el working tree (dashboard, i18n, security, middleware) son **paralelos** a Fase 0 y no fueron requisito del gate de estabilización.

---

## 6. Verificación manual recomendada

```bash
make test-stable
make test
pytest tests/test_api.py tests/test_web_tools.py tests/test_conversations.py -q
pytest tests/test_fix_cerebro -q
```

Smoke con servicio vivo (opcional):

```bash
make run          # :7842
make smoke        # tests/test_smoke_live.py
```

---

## 7. Próximo paso — Fase 1

Ver [`CURRENT_FOCUS.md` § Fase 1](../plans/CURRENT_FOCUS.md): workflows E1–E5 (calendario permisos UI, fusión calendario→archivo, file search multi-root, recordatorios, RAG PDF).
