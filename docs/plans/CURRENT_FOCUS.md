# Plan vigente — Cerebro v0.2

> **Última revisión:** 2026-06-22  
> **Horizonte:** 4–6 semanas, un desarrollador, Mac M1 8 GB  
> **Este documento es la fuente de verdad:** evaluación estratégica + recomendaciones + plan de ejecución.

Planes ambiciosos archivados en [`maybe-later/`](maybe-later/).

---

## 1. Evaluación honesta del proyecto

Análisis basado en arquitectura, tests, commits, y estado real del código (no solo el README).

### Lo bueno

| Área | Por qué importa |
|------|-----------------|
| **Arquitectura con criterio** | No es un wrapper de ChatGPT. Hay capas reales: inferencia (llama.cpp/MLX/Claude), memoria (corto/largo/vector), agentes especializados, RAG, política de herramientas, confirmación humana, LangGraph con límites duros. Más maduro que el 90% de proyectos "local AI assistant" en GitHub. |
| **Fast paths** | El router determinista (math → file write → calendario → búsqueda → LLM) es la mejor decisión técnica. Resuelve en milisegundos lo que un 2B haría mal o lento. Tests de regresión (`make test-stable`) y docs congeladas del orden del pipeline. |
| **Cultura de testing** | ~78 archivos de test, cientos de casos, mocking a nivel `AppState`. La intención y la cobertura están ahí. |
| **Honestidad con el hardware** | M1 8 GB como constraint real: RAM preflight, perfiles lite, Low Power marcado como no shipped. |
| **Integración macOS nativa** | Calendario + recordatorios + fusión calendario→archivo. LM Studio, Ollama y la mayoría de chatbots locales no lo tienen. |
| **Seguridad pensada** | Confirmación de tools peligrosas, sandbox, audit, planes de hardening. Importante para un OS personal que ejecuta código. |

### Lo malo (o lo que frena)

| Problema | Impacto |
|----------|---------|
| **Scope creep** | Cognitive OS, fleet, low power, knowledge sync, automation, time-travel debugger, dashboard redesign, i18n completo, LoRA, SmolLM2… son 3–4 productos en uno. |
| **God files** | `runtime.py` (~1.9k líneas), `server.py` (~2.3k), `main.py` (~800). Cada cambio aumenta riesgo de regresión. |
| **Brecha visión ↔ ejecución** | El README vendía "Cognitive Operating Layer". El código entrega un asistente local con buenos fast paths y calendario. |
| **macOS-only de facto** | El 80% del valor diferencial no porta sin reescribir media capa. |
| **Modelo pequeño = cuello de botella** | Qwen3.5-2B en 8 GB es usable pero frágil en tool calling. El loop agentico es la parte más débil frente a los fast paths. |
| **Documentación > producto** | Miles de líneas en `docs/plans/` antes de consolidar. Ayuda al arquitecto, no al usuario diario. |
| **Suite no verde** | ~~Full test run: ~1093 passed, ~51 failed~~ → **Fase 0:** `make test` 1138 passed, `make test-stable` 154 passed (2026-06-22). |

### ¿Vale la pena?

| Objetivo | Veredicto |
|----------|-----------|
| Aprender / portfolio / base personal | **Sí.** Demuestra arquitectura real, testing, constraints de hardware, integración OS. |
| Producto comercial vs ChatGPT/Claude | **No ahora.** No compites en razonamiento ni ecosistema. |
| Herramienta diaria (power user Mac 8 GB) | **Casi.** Si consolidas 2–3 workflows killer, sí. |
| Open source con comunidad | **Posible en nicho**, no como "otro LM Studio". |

**Conclusión:** No es un proyecto perdido. Es un proyecto **demasiado ambicioso para su etapa**, pero con cimientos mejores que muchos.

### ¿Se ve realista?

**Parcialmente — y eso es bueno si ajustas expectativas.**

| Realista hoy | No realista a corto plazo (6–12 meses solo) |
|--------------|---------------------------------------------|
| Asistente local con chat + streaming + historial | Cognitive OS completo |
| Fast paths (calendario, archivos, math) | Competir con Obsidian en knowledge graph |
| RAG sobre documentos indexados | Fleet multi-modelo fluido en 8 GB |
| Tool loop con confirmación | Automation tipo Rewind/Apple Intelligence |
| UI Tauri funcional | Producto pulido para usuarios no técnicos |
| Tests automatizados | |

---

## 2. Posicionamiento acordado

### Qué es Cerebro *ahora*

No es un Cognitive OS ni un clon de Obsidian. Es:

- Chat local con streaming + historial
- **Fast paths** deterministas (math, calendario, archivos, recordatorios)
- RAG sobre documentos indexados
- Tool loop con confirmación humana para acciones peligrosas
- Integración macOS: Calendar, archivos, recordatorios
- UI Tauri + API REST en `:7842`

### Wedge defendible (mensaje público)

> **Cerebro: el asistente local que ejecuta acciones reales en tu Mac — calendario, archivos y recordatorios — con respuestas instantáneas cuando puede y LLM solo cuando hace falta.**

No competir en "chat inteligente". Competir en **"hace cosas en tu Mac sin mandar datos a la nube y sin mentir"**.

### Qué destacaría hoy (siendo realistas)

1. **Fast paths en acción** — Misma pregunta en ChatGPT vs Cerebro: "¿qué tengo el viernes?" → Cerebro en ~50 ms leyendo Calendar real.
2. **"Built for 8GB M1"** — Casi nadie optimiza para eso. Benchmark honesto: RAM, latencia, modelos que caben.
3. **Fusión calendario → archivo** — "Exporta mi semana a markdown en Desktop" funcionando de verdad. Es workflow, no chat.

### Qué NO destacaría (aún)

- Fleet orchestrator
- Cognitive graph / Obsidian clone
- Low Power mode (hasta shipped)
- "26 herramientas" (suena a bloat; mostrar 5 que funcionan perfecto)

---

## 3. Qué cambiar y qué no cambiar

### Cambiar

| # | Acción | Motivo |
|---|--------|--------|
| 1 | **Un solo wedge** — calendario + archivos + recordatorios en Mac | Todo lo demás → `maybe-later/` |
| 2 | **Partir `runtime.py` y `server.py`** (cuando tests verdes) | Supervivencia, no estética |
| 3 | **Priorizar LoRA tool calling** — solo *después* de v0.2 | Multiplicador de calidad en el 30% que va al LLM |
| 4 | **Definir "done" con 5 escenarios E2E** | Ver sección 4 |
| 5 | **Reducir planes activos** | Un plan de ejecución (`CURRENT_FOCUS.md`) + specs incrementales |
| 6 | **Arreglar tests rotos antes del siguiente feature** | Señal de contratos rotos en refactor |

### No cambiar

| Pieza | Por qué |
|-------|---------|
| Fast paths + orden del pipeline | Moat técnico; ventaja de latencia y confiabilidad |
| Local-first + confirmación de tools | Diferenciador de confianza vs cloud |
| LangGraph con límites duros | Correcto para agentes en hardware limitado |
| Stack llama.cpp + FastAPI + Tauri | Adecuado para Mac 8 GB |
| Tests con mocks a `AppState` | Patrón correcto y mantenible |
| Integración calendario macOS | Killer feature potencial; pocos lo hacen bien |
| Filosofía Nano Mode v2 ("0.5B = chat, no agente") | Insight correcto; diseño en `maybe-later/` |

---

## 4. Definición de "hecho" — v0.2

Estos 5 escenarios deben pasar **siempre** (manual + tests):

| # | Usuario dice | Resultado esperado |
|---|--------------|-------------------|
| E1 | "¿Qué tengo mañana?" | Eventos reales del calendario, no alucinación |
| E2 | "Crea un archivo con mis reuniones de esta semana" | Archivo en `CEREBRO_FILES_PATH` vía fusión calendario→archivo |
| E3 | "Busca PDFs sobre X en Desktop" | `search_files` con resultados reales |
| E4 | "Recuérdame comprar leche a las 6" | Recordatorio creado (con confirmación si aplica) |
| E5 | "Resume este PDF" (archivo indexado) | RAG devuelve resumen basado en chunks, no inventado |

**Gate de release:** `make test-stable` verde + E1–E5 en smoke manual.

**Regla de oro:**

> Una feature nueva solo entra si los 5 escenarios E1–E5 siguen pasando. Si un cambio rompe un fast path estable, revertir antes de seguir.

---

## 4.1 Completado recientemente

### Engine / backend split (2026-06-25) ✅

Separar backend (`:7842`) y motor LLM (`:8080`) para ahorrar RAM en M1 8 GB.

| Entregable | Estado |
|------------|--------|
| `make run` sin auto-start motor | ✅ |
| API `/api/engine/start\|stop\|status` | ✅ |
| Scripts `desktop-backend` / `desktop-engine` | ✅ |
| Tauri: backend al abrir app | ✅ |
| UI: Start/Stop engine (no todo el stack) | ✅ |
| Docs | [`engine-backend-split.md`](engine-backend-split.md), [`engine-backend-split-phase4-5.md`](../implementation/engine-backend-split-phase4-5.md) |

---

## 5. Organización de la documentación

| Ubicación | Contenido |
|-----------|-----------|
| **`CURRENT_FOCUS.md`** (este archivo) | Evaluación + estrategia + plan de ejecución |
| [`implementation-roadmap.md`](implementation-roadmap.md) | Índice y estado del proyecto |
| [`maybe-later/`](maybe-later/) | 28 planes archivados: cognitive OS, fleet, low power, knowledge sync, optimización, dashboard redesign, fix plans históricos |
| Specs incrementales activas | `file-search-multi-root.md`, `i18n-implementation.md` (parcial), `SECURITY_AUDIT_RESULTS.md` |

**Criterio para sacar algo de `maybe-later/`:**

1. `make test` y `make test-stable` en verde.
2. E1–E5 pasan de forma fiable.
3. RAM/latencia medida en M1 8 GB real.

---

## 6. Plan de ejecución (4–6 semanas)

### Fase 0 — Estabilizar (semana 1) ✅ COMPLETADA (2026-06-22)

**Objetivo:** Suite de tests en verde; no añadir features.

| Tarea | Estado |
|-------|--------|
| Arreglar tests de config API | ✅ |
| Arreglar tests web tools | ✅ |
| Arreglar calendar birthday edge case + fusion | ✅ |
| `_is_small_model()` (regex rompía tool loop con Qwen3.5-2B) | ✅ |
| `make test-stable` + `make test` en verde | ✅ **1138 passed**, cov 72% |

**Nota:** Dashboard/i18n no se congeló (ya en curso / parcialmente hecho).

**Documentación detallada:** [`docs/implementation/phase-0-stabilization.md`](../implementation/phase-0-stabilization.md)

```bash
make test-stable   # 154 passed
make test          # 1138 passed (-m "not live")
```

---

### Fase 1 — Core workflows (semanas 2–3)

**Objetivo:** Los 5 escenarios E1–E5 fiables.

| Prioridad | Tarea | Esfuerzo |
|-----------|-------|----------|
| P1 | Calendario: permisos macOS visibles en UI + mensajes claros si denegado | 1–2 días |
| P2 | Fusión calendario→archivo: regresión + prompts estables | 1 día |
| P3 | File search multi-root (Desktop, Documents) — [`file-search-multi-root.md`](file-search-multi-root.md) | 1–2 días |
| P4 | Recordatorios: fast path + confirmación UI | 1 día |
| P5 | RAG: indexar + preguntar sobre PDF indexado (smoke E5) | 1 día |

```bash
make test-stable
pytest tests/test_calendar*.py tests/test_file_write_calendar_fusion.py tests/test_file_search*.py -q
```

---

### Fase 2 — UX mínima usable (semana 4)

**Objetivo:** Alguien no técnico puede usarlo sin leer 10 docs.

| Tarea | Detalle |
|-------|---------|
| Wizard de primer arranque estable | Modelo + carpetas + permisos calendario |
| Botones rotos conectados | Nuevo chat, borrar conversación, guardar settings |
| Estado del engine visible | RAM, modelo cargado, health llama.cpp |
| Mensajes de error en español | i18n mínimo en errores de tools (no UI completa) |

Referencia: [`i18n-implementation.md`](i18n-implementation.md) — **solo errores y wizard**, no traducir toda la UI.

---

### Fase 3 — Calidad y confianza (semanas 5–6)

| Tarea | Detalle |
|-------|---------|
| Security baseline | Items P0 de [`SECURITY_AUDIT_RESULTS.md`](SECURITY_AUDIT_RESULTS.md) |
| Smoke script E2E | `scripts/smoke.sh` cubre E1–E5 |
| README honesto | Sin promesas de features no shipped |
| Partir `server.py` (opcional) | `api/query.py`, `api/config.py` — solo si Fase 0–2 verdes |

---

## 7. Qué implementar ahora (orden concreto)

Si solo tienes un bloque de trabajo, seguir este orden:

1. **`pytest tests/test_api.py -q`** → arreglar config GET/PATCH (rompe settings en UI).
2. **`make test-stable`** → si falla calendario, priorizar sobre web tools.
3. **Smoke manual E1** — "¿qué tengo mañana?" con llama.cpp vivo; anotar si falla por permiso vs routing.
4. **No tocar** fleet, low power, dashboard nuevo, knowledge sync.
5. Cuando la suite esté verde → **file-search multi-root** (alto impacto, bajo riesgo).
6. Después → fusión calendario→archivo (E2) y recordatorios (E4).
7. Cerrar con RAG sobre PDF (E5) y wizard de permisos (Fase 2).

---

## 8. Backlog explícito (después de v0.2)

Solo retomar cuando v0.2 esté shipped:

| ID | Qué | Diseño |
|----|-----|--------|
| L1 | LoRA tool calling Qwen3.5-2B | `maybe-later/` |
| L2 | Low Power Nano Mode v2 | `maybe-later/LOW_POWER_V2_NANO_MODE.md` |
| L3 | Fleet orchestrator | `maybe-later/LOCAL_MODEL_FLEET_ORCHESTRATOR.md` |
| L4 | Knowledge sync ampliado | `maybe-later/knowledge_sync_agent.md` |
| L5 | Cognitive OS / graph | `maybe-later/future-cognitive-os.md` |
| L6 | Windows port | `maybe-later/` |
| L7 | Dashboard redesign | `maybe-later/DASHBOARD_REDESIGN.md` |
| L8 | SmolLM2 classifier / 0.8B worker | `maybe-later/Qwen3.5-0.8B-integration-ideas.md` |

---

## 9. Métricas de éxito

| Métrica | Objetivo v0.2 |
|---------|---------------|
| `make test` | 0 fallos |
| `make test-stable` | 0 fallos |
| E1–E5 manual | 5/5 consistentes |
| RAM con chat activo | < 6 GB total (macOS + llama + backend) |
| Latencia fast path | < 200 ms |
| Latencia calendario | < 3 s (incl. AppleScript) |

---

## 10. Resumen en una frase

**Cerebro es un proyecto serio con arquitectura de producto real. Si se enfoca en "asistente local confiable para calendario + archivos en Mac 8 GB", tiene un nicho defendible. El trabajo inmediato es estabilizar tests y cerrar los 5 escenarios E1–E5 — no añadir más visión.**
