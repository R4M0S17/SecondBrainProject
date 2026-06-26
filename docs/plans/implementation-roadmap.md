# Implementation Roadmap — índice

> **Este archivo ya no es el backlog activo.**  
> **Fuente de verdad (evaluación + estrategia + ejecución):** [`CURRENT_FOCUS.md`](CURRENT_FOCUS.md)

---

## Estado del proyecto (2026-06)

| Área | Estado |
|------|--------|
| Fast paths (math, calendario, archivos) | ✅ Estable — `make test-stable` |
| LangGraph agent loop | ⚠️ Funcional; tool calling frágil en 2B |
| RAG + indexación | ✅ Implementado |
| UI Tauri + chat | ✅ Funcional |
| Fleet / multi-modelo | 🔒 Congelado → [`maybe-later/`](maybe-later/) |
| Low Power 0.5B | 🔒 En desarrollo, no shipped |
| Cognitive OS / graph | 🔒 Visión → [`maybe-later/future-cognitive-os.md`](maybe-later/future-cognitive-os.md) |
| Tests completos | ⚠️ ~51 fallos (refactor en curso) |

---

## Documentos activos

| Documento | Uso |
|-----------|-----|
| [`CURRENT_FOCUS.md`](CURRENT_FOCUS.md) | **Único plan de ejecución** (4–6 semanas) |
| [`file-search-multi-root.md`](file-search-multi-root.md) | Spec incremental — Fase 1 |
| [`i18n-implementation.md`](i18n-implementation.md) | Solo errores + wizard en v0.2 |
| [`SECURITY_AUDIT_RESULTS.md`](SECURITY_AUDIT_RESULTS.md) | P0 items — Fase 3 |
| [`web-search-tavily.md`](web-search-tavily.md) | Opcional; web search no es wedge |
| [`new_fast_paths_implementation.md`](new_fast_paths_implementation.md) | Referencia; muchos ya implementados |

---

## Archivado (quizás más adelante)

Todo en [`maybe-later/`](maybe-later/) — visión, fleet, low power, knowledge sync, optimización, estabilización histórica, dashboard redesign.

Incluye los planes que antes vivían aquí como H1–H8 (LoRA, SmolLM2 classifier, 0.8B worker, knowledge sync agent, Windows port, etc.).

**No ejecutar esos planes hasta v0.2 shipped.**

---

## Orden histórico (referencia)

El roadmap anterior priorizaba: Knowledge Sync → Calendar → Web → Fast Paths → LoRA → Fleet.

**Nuevo orden:** Estabilizar tests → E1–E5 workflows → UX mínima → security P0 → *entonces* considerar LoRA/fleet desde `maybe-later/`.
