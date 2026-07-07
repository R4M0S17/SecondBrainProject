# Planes archivados — quizás más adelante

Estos documentos **no son prioridad activa**. Se conservan como referencia de visión, investigación o trabajo histórico.

**Plan vigente:** [`../CURRENT_FOCUS.md`](../CURRENT_FOCUS.md)

## Por qué están aquí

| Categoría | Documentos | Motivo |
|-----------|------------|--------|
| **Visión a largo plazo** | `future-cognitive-os.md`, `ideas-future.md` | Ideas ambiciosas — 2–3 años, no v0.2 |
| **Multi-modelo / fleet** | `LOCAL_MODEL_FLEET_ORCHESTRATOR.md`, `FLEET_ORCHESTRATOR_*` | Complejidad alta en 8 GB; el modo simple basta por ahora |
| **Low Power / Nano** | `LOW_POWER_MODE_0.5B.md`, `LOW_POWER_V2_NANO_MODE.md` | Diseño correcto pero no shipped; enfocar 2B estable primero |
| **Knowledge sync** | `knowledge_sync_agent.md`, `knowledge_sync_v2_improvements.md` | Parcialmente implementado; no ampliar hasta core workflows verdes |
| **Optimización backend** | `Optimization_*`, `Llama_backend_optimization_path.md`, `per_request_n_ctx.md` | Prematuro sin producto estable |
| **Estabilización histórica** | `fix-cerebro.md`, `fix-plan-v2.md`, `impleme-fix*` | Muchas fases ya mergeadas; referencia, no backlog activo |
| **Integraciones cloud** | `CLAUDE_API_*` | Ya integrado en código; docs de implementación obsoletas |
| **UI grande** | `DASHBOARD_REDESIGN.md`, `FRONTEND_STATUS_DIAGNOSIS.md` | Rediseño masivo; pausar hasta v0.2 estable |
| **Otros** | `docker-plug-and-play.md`, `Agentic_implementation.md`, `Qwen3.5-0.8B-*`, `semantic_context_compressor.md`, `plan_cerebro_implementacion.md` | Nice-to-have o ya hecho |

## Cuándo rescatar un plan

1. `make test` y `make test-stable` en verde.
2. Los 5 escenarios E2E de [`CURRENT_FOCUS.md`](../CURRENT_FOCUS.md) pasan de forma fiable.
3. Hay RAM/latencia medida y documentada en hardware real (M1 8 GB).
