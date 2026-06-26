# Plans & roadmaps

## Empieza aquí

| Documento | Qué es |
|-----------|--------|
| **[`CURRENT_FOCUS.md`](CURRENT_FOCUS.md)** | **Documento maestro** — evaluación honesta, qué cambiar/no cambiar, posicionamiento, plan v0.2 |
| [`implementation-roadmap.md`](implementation-roadmap.md) | Índice + estado; apunta a CURRENT_FOCUS |
| [`maybe-later/`](maybe-later/) | Visión, fleet, cognitive OS, low power, etc. — **no prioridad** |

---

## Specs activas (incrementales)

| Documento | Cuándo usar |
|-----------|-------------|
| [`engine-backend-split.md`](engine-backend-split.md) | **Separar backend (`:7842`) y motor LLM (`:8080`)** — plan de implementación |
| [`file-search-multi-root.md`](file-search-multi-root.md) | Fase 1 — ampliar búsqueda a Desktop/Documents |
| [`workflows-tab-implementation.md`](workflows-tab-implementation.md) | **Pestaña Flujos** — grabación UI, recetas, diseño cybernetic (4 fases) |
| [`i18n-implementation.md`](i18n-implementation.md) | Fase 2 — errores y wizard primero |
| [`SECURITY_AUDIT_RESULTS.md`](SECURITY_AUDIT_RESULTS.md) | Fase 3 — hardening P0 |
| [`SECURITY_HARDENING_PLAN.md`](SECURITY_HARDENING_PLAN.md) | Detalle de seguridad (referencia) |
| [`web-search-tavily.md`](web-search-tavily.md) | Opcional; no bloquea v0.2 |
| [`new_fast_paths_implementation.md`](new_fast_paths_implementation.md) | Referencia fast paths ya hechos |

---

## Archivado — quizás más adelante

[`maybe-later/README.md`](maybe-later/README.md) explica qué hay y por qué no es backlog activo:

- Cognitive OS, ideas futuras
- Fleet orchestrator, Low Power Nano
- Knowledge sync (plan grande)
- Optimización backend, Docker, Windows port
- Dashboard redesign, fix plans históricos
- Claude API integration docs (ya en código)

---

## Related

- Manual QA: [`../testing/`](../testing/)
- Incidents: [`../incidents/`](../incidents/)
- Fast paths (congelados): [`../architecture/fast-paths.md`](../architecture/fast-paths.md)
