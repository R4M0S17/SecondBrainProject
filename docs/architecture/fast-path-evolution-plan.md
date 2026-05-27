## Fast paths: plan de evolución segura (archivos, calendario y futuros módulos)

Este documento define **cómo añadir nuevas capacidades** (fast paths) sin romper las que ya funcionan bien hoy: creación de archivos y calendario.

Se divide en tres fases, pensadas para implementarse en **dos commits separados**:

- **Paso 1 (Commit 1)**: Fase 1 + Fase 2 → documentación + tests estables.
- **Paso 2 (Commit 2)**: Fase 3 → refactor al router, sin cambiar el comportamiento.

La idea es que los tests de la Fase 2 actúen como un **candado matemático**: si siguen en verde después de la Fase 3, el refactor no rompió nada.

---

### Estado actual (resumen)

El flujo principal en `AgentRuntime.run()` es, en orden:

1. **Math fast path** (`try_pure_math_fast_path`)
2. **File write fast path** (`_resolve_file_write_intent` → `file_write_fast_path` + `file_write_calendar_fusion`)
3. **Reminder intent (LLM + tools)** (`_try_reminder_llm_resolve`)
4. **Calendar fast path** (`try_calendar_fast_path`)
5. **File search fast path** (`try_file_search_fast_path`)
6. Si nada aplica → **loop con LLM + herramientas**

Los fast paths de **archivos** y **calendario** ya están probados, tanto con tests unitarios como con scripts live (`scripts/test_file_write_llamacpp.py`, etc.).

---

## Fase 1 — Documentación y contrato de fast paths ✅ DONE

**Estado:** completada (2026-05-26).

**Objetivo**: Congelar el diseño actual en texto, para que cualquier cambio futuro sea intencional y revisable.

- [x] `docs/architecture/fast-paths.md` — orden, módulos, herramientas, salidas, prioridades.
- [x] `docs/architecture/stable-prompts.md` — prompts validados en UI (archivos, calendario, regresiones).
- [x] `docs/architecture/adding-a-fast-path.md` — checklist para nuevas capacidades.
- [x] `docs/README.md` — enlaces al índice de arquitectura.
- [x] `.cursor/rules/cerebro.mdc` — regla de no romper fast paths estables sin regresión.

**Riesgo**: nulo; solo documentación.

---

## Fase 2 — Suite “test-stable” sin llama.cpp (candado de regresión) ✅ DONE

**Estado:** completada (2026-05-26).

**Objetivo**: Tener una batería de tests **rápidos, deterministas y sin llama.cpp** que congelen el comportamiento de archivos y calendario.

### 2.1. Tests parametrizados de fast paths

- Crear `tests/fixtures/stable_fast_path_prompts.yaml` (o similar):
  - Cada entrada contiene:
    - `prompt`: texto del usuario.
    - `expected_fast_path`: `file_write`, `file_write_calendar_fusion`, `calendar_read`, `none`, …
    - `expected_content_source`: `spec` o `literal`.
    - Campos opcionales:
      - `must_contain`: lista de substrings que deben aparecer en el cuerpo generado.
      - `must_not_contain`: substrings que no deben aparecer (por ejemplo, la frase literal del prompt).

- Crear `tests/test_stable_fast_paths.py`:
  - Tests que **solo** llaman a funciones puras / deterministas:
    - `parse_file_write_intent`, `classify_file_content`, `is_content_specification`.
    - `try_file_write_fast_path`, `try_file_write_calendar_fusion`.
    - `try_calendar_fast_path`, `filter_events_by_date`, parsers de calendario.
  - Validan que cada prompt de `stable_fast_path_prompts.yaml` produce:
    - El fast path esperado.
    - El tipo de contenido esperado (`spec` vs `literal`).
    - El cuerpo correcto (cuando aplique).

### 2.2. Regla crítica: **sin llama.cpp** en test-stable

Recomendación arquitecto (a aplicar explícitamente aquí):

- `make test-stable` **no debe nunca**:
  - Levantar llama.cpp.
  - Hacer embeddings caros.
  - Llamar a backends externos.
- Implementación práctica:
  - Tests de Fase 2 usan **solo Python/regex y lógica local**.
  - Para funciones que normalmente piden LLM (p. ej. generar código a partir de spec), se usan **mocks** de `chat.complete` y amigos.
  - Scripts como `scripts/test_file_write_llamacpp.py` quedan fuera de `test-stable` y se ejecutan manualmente o en otra diana (`make test-live`).

Esto es especialmente importante en tu entorno (Mac M1 8GB): un test que accidentalmente lance llama.cpp o haga embeddings pesados puede congelar la máquina.

### 2.3. Comando en Makefile

- Añadir en `Makefile`:

  - `make test-stable`: corre solo los tests marcados como “estables”:
    - Por ejemplo: `pytest -q -m stable` o una lista explícita de ficheros clave (`test_file_write_fast_path`, `test_file_write_calendar_fusion`, `test_calendar_fast_path`, `test_stable_fast_paths`, etc.).
  - Mantener `make test` como suite completa, más lenta.

**Riesgo**: bajo (solo tests y Makefile).  
**Beneficio**: cualquier cambio que rompa archivos o calendario se ve de inmediato, sin necesidad de levantar llama.cpp.

---

## Fase 3 — Router explícito de fast paths (sin cambiar comportamiento) ✅ DONE

**Estado:** completada (2026-05-26).

**Objetivo**: Extraer la lógica de orden y selección de fast paths desde `AgentRuntime.run()` / `run_streaming()` a un **router dedicado**, manteniendo exactamente el mismo comportamiento.

Este trabajo debe ir en **un commit separado**, después de que Fase 1 + 2 estén en verde y el diseño actual esté “congelado”.

### 3.1. Nuevo módulo: `core/agents/fast_path_router.py`

Concepto clave: un **router de fast paths** con una interfaz uniforme:

- Cada handler registra:
  - `name`: cadena (`"math"`, `"file_write"`, `"reminder_intent"`, `"calendar_read"`, `"file_search"`, …).
  - `try_fn`: función con firma homogénea, por ejemplo:

    ```python
    async def try_fn(query: str, agent_state: AgentState) -> FastPathResult | None
    ```

  - `priority`: entero que define el orden (se inicializa con los valores actuales).
  - Opcional: flag/env var para habilitar/deshabilitar módulos experimentales.

- **Definir bien qué significa que un handler “gane”**:
  - Contrato propuesto para `FastPathResult` (a nivel de diseño, no de código todavía):
    - `kind`: `"answer"` | `"pending_tool"` | `"skip"`.
    - `answer`: texto al usuario (si aplica).
    - `pending_tool_name` / `pending_tool_args`: si corresponde.
    - `inference_warnings`: lista de tags a añadir.

  El punto importante aquí es que **todos los handlers usen el mismo contrato**; hoy cada fast path toca directamente `AgentRuntime` (`append_inference_warnings`, `pending_tool`, etc.).

### 3.2. Integración en `AgentRuntime.run()`

- Reemplazar el bloque:

```python
fast_answer = self._try_math_fast_path(...)
...
file_intent = await self._resolve_file_write_intent(...)
...
reminder_result = await self._try_reminder_llm_resolve(...)
...
calendar_answer = self._try_calendar_fast_path(...)
...
file_search_answer = self._try_file_search_fast_path(...)
```

por una única llamada al router, por ejemplo:

```python
result = await fast_path_router.try_all(query, agent_state)
```

**condición de diseño para este commit**:

- El router **debe replicar exactamente el orden y la lógica actual**:
  - Misma prioridad: math → file_write (+ calendar fusion) → reminder → calendar_read → file_search.
  - Misma forma de escribir en `short_term`, `pending_tool`, `inference_warnings`.
- No se introducen fast paths nuevos en esta fase, solo se mueve código.

### 3.3. Uso de los tests de Fase 2 como “prueba matemática”

Recomendación clave del plan:

- Antes de mover nada:
  - `make test-stable` en verde.
- Después de introducir el router y adaptar `run()` / `run_streaming()`:
  - **Sin tocar los tests de Fase 2**, volver a ejecutar:

    ```bash
    make test-stable
    ```

  - Si sigue en verde, significa que el refactor **no cambió el comportamiento observable** de los fast paths.
  - Cualquier divergencia (por ejemplo, un prompt que antes caía en file_write y ahora cae en calendar_read) se verá inmediatamente.

### 3.4. Detalles de contrato a fijar en el diseño

Para reducir riesgos en la implementación:

- Especificar en este doc (o en un anexo) el contrato exacto de `try_fn` y `FastPathResult`:
  - ¿Es `async` o `sync`? (probablemente `async` para no bloquear).
  - ¿Puede escribir en `AgentState`, o solo devuelve datos puros?
  - ¿Quién se encarga de:
    - Pushear mensajes en `short_term`.
    - Guardar `AgentState`/`ConversationStore`.
    - Añadir `inference_warnings`.
- Idealmente:
  - El router decide **qué fast path gana** y devuelve solo datos.
  - `AgentRuntime` aplica esos datos (mutación de estado, métricas, etc.), manteniendo todo en un solo lugar.

**Riesgo**: medio, pero acotado por:

- No se cambia el orden ni se añaden capacidades nuevas.
- Los tests de Fase 2 deben quedar verdes antes y después.
- Los scripts live (`scripts/test_file_write_llamacpp.py`, etc.) se pueden usar como smoke adicional.

---

## Resumen de ejecución (A + B, commits separados)

1. **Commit 1 — Fase 1 + Fase 2**
   - Añadir documentación (`fast-paths.md`, `stable-prompts.md`, `adding-a-fast-path.md`).
   - Crear tests y fixtures para `make test-stable` (sin llama.cpp, todo mockeado).
   - Dejar `make test-stable` verde.

2. **Commit 2 — Fase 3 (router)**
   - Introducir `fast_path_router.py` y adaptar `AgentRuntime.run()` / `run_streaming()` para usarlo.
   - No introducir fast paths nuevos.
   - Ejecutar:
     - `make test-stable`
     - Idealmente también `make test` completo.
   - Confirmar que los prompts estables (archivos y calendario) se comportan igual que antes.

Con esto, archivos y calendario quedan **protegidos**: cualquier nueva capacidad futura se enchufa como un handler adicional en el router, con flag si hace falta, y si algo rompe lo que ya funciona, `make test-stable` lo detecta de inmediato.
