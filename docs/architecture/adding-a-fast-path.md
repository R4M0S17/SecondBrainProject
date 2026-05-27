# Adding a fast path — checklist

Guía para añadir una capacidad nueva **sin romper** file write, calendario ni búsqueda de archivos.

Referencias: [`fast-paths.md`](fast-paths.md) · [`stable-prompts.md`](stable-prompts.md) · [`fast-path-evolution-plan.md`](fast-path-evolution-plan.md)

---

## Antes de escribir código

### 1. Definir el dominio

- [ ] ¿Qué problema resuelve? (ej. enviar email, indexar carpeta, ejecutar script)
- [ ] ¿Es **lectura**, **escritura** o **generación**?
- [ ] ¿Necesita confirmación del usuario?

### 2. Detectar solapamiento con fast paths estables

| Pregunta | Si “sí” → |
|----------|-----------|
| ¿El usuario puede decir “crea un archivo…”? | **No** insertar antes del paso 2 (file write). Revisar regex compartidos. |
| ¿Menciona calendario / cumpleaños / agenda? | Coordinar con `calendar_fast_path` y `file_write_calendar_fusion`. |
| ¿Menciona “busca archivos” o rutas? | Coordinar con `file_search_fast_path` (tiene guard anti-write). |
| ¿Es aritmética pura? | Solo antes de math si es estrictamente numérico. |

### 3. Elegir posición en el pipeline

Orden actual (no cambiar sin revisión explícita):

```text
math → file_write → reminder → calendar_read → file_search → LLM
```

| Tipo de feature | Posición recomendada |
|-----------------|----------------------|
| Exportar datos externos a archivo | Extender fusion o sub-módulo llamado desde `_resolve_file_write_intent` |
| Consulta read-only nueva | Después de calendar_read, antes de file_search (o después de file_search si compite con “busca”) |
| Acción con confirmación | Patrón reminder: LLM extract opcional + `pending_tool` |
| Experimental / arriesgado | Mismo orden pero detrás de `CEREBRO_ENABLE_<FEATURE>=true` (Fase 4 del plan) |

**Nunca** colocar un parser genérico “catch-all” en posición 1–2.

---

## Implementación

### 4. Un módulo por feature

```text
core/agents/<feature>_fast_path.py   # parse + try_* puro
tests/test_<feature>_fast_path.py    # unit tests, sin llama.cpp
```

Reglas:

- [ ] Función pública: `try_<feature>_fast_path(query, authorized_tools, ...) -> Result | None`
- [ ] `None` = no match; el runtime continúa al siguiente handler
- [ ] **No** meter lógica de email/RAG/shell dentro de `file_write_fast_path.py` o `calendar_fast_path.py`
- [ ] Duplicar cambios en `cerebro/core/agents/` si usas ese árbol

### 5. Hook mínimo en runtime

- [ ] Un método `_try_<feature>_fast_path` o entrada en router (Fase 3)
- [ ] Reutilizar `_finish_*` existentes cuando la salida sea `answer` o `pending_tool`
- [ ] Añadir `append_inference_warnings(["<feature>_fast_path"])`
- [ ] `mark_skip_context_enricher()` si aplica (como otros fast paths)

### 6. Herramientas y agentes

- [ ] Registrar handler en `core/tools/registry.py` si es tool nueva
- [ ] Añadir a `specialized.py` solo si un agente concreto la necesita
- [ ] `requires_confirmation=True` en `ToolDefinition` si es destructiva/escritura

---

## Tests (obligatorio)

### 7. Tests unitarios — sin llama.cpp

- [ ] Parser: prompts que **sí** matchean y prompts que **no** deben matchear
- [ ] Mocks para cualquier `chat.complete` o subprocess
- [ ] Tests de regresión: correr suite file + calendar existente

Comando actual (hasta Fase 2):

```bash
.venv/bin/python -m pytest -q \
  tests/test_file_write_fast_path.py \
  tests/test_file_write_calendar_fusion.py \
  tests/test_calendar_fast_path.py \
  tests/test_file_search_fast_path.py
```

Comando futuro: `make test-stable`

### 8. Añadir prompts estables

- [ ] Entrada en [`stable-prompts.md`](stable-prompts.md)
- [ ] (Fase 2) Entrada en `tests/fixtures/stable_fast_path_prompts.yaml`

### 9. E2E manual (opcional pero recomendado)

- [ ] Nota en `manual_tests/e2e/<feature>_YYYY-MM-DD.md`
- [ ] Script live **fuera** de `test-stable` si usa llama.cpp

---

## Revisión pre-merge

- [ ] ¿Algún regex nuevo comparte palabras con `_SPEC_HINT_RE`, calendario o file search?
- [ ] ¿El orden del pipeline sigue el de `fast-paths.md`?
- [ ] ¿Los prompts de `stable-prompts.md` siguen pasando?
- [ ] ¿Documentación actualizada si cambia prioridad o warnings?

---

## Anti-patrones (evitar)

| Anti-patrón | Por qué rompe |
|-------------|---------------|
| Mega-regex en runtime | Roba prompts de file/calendar |
| “Si contiene archivo → write” | Falso positivo en búsqueda |
| Ampliar `_SPEC_HINT_RE` sin tests | Literal vs spec se desbalancea |
| LLM decide si crear archivo | Ya resuelto por fast path; reintroduce alucinaciones |
| Refactor grande de runtime sin Fase 2 | Sin candado de regresión |
| Solo editar `core/` o solo `cerebro/` | Comportamiento distinto según entry point |

---

## Plantilla rápida (copiar en PR)

```markdown
## Fast path: <nombre>

- **Posición en pipeline:** después de ___ , antes de ___
- **Módulo:** `core/agents/____fast_path.py`
- **Solapamiento revisado:** file write ☐ calendar ☐ file search ☐
- **Confirmación:** sí / no
- **Tests:** `tests/test_____fast_path.py`
- **Stable prompts añadidos:** sí / no (enlace)
- **Regresión:** pytest file + calendar en verde
```
