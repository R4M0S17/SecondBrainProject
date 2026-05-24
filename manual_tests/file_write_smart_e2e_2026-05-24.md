# E2E — Creación de archivos inteligente (2026-05-24)

Mejora pedida en `manual_tests/frontend_chat_qwen3_2026-05-24.md` (ítem 4): no guardar literalmente descripciones ni bloques markdown con fences.

| Campo | Valor |
|--------|--------|
| Backend | Cerebro `:7842` + llama.cpp `:8080` |
| Modelo | `Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf` |
| Carpeta escritura | `~/Desktop/CerebroFiles` |
| Tests auto | `tests/test_file_write_fast_path.py` — **12 passed** |

---

## Cambios implementados

| Archivo | Rol |
|---------|-----|
| `core/agents/file_write_fast_path.py` | Clasifica contenido: `literal`, `fenced`, `spec`; extensión `.py`; rechaza nombres inválidos (`de`, etc.) |
| `core/agents/file_content_generator.py` | Genera cuerpo del archivo vía LLM cuando el usuario describe el contenido |
| `core/agents/runtime.py` | `_resolve_file_write_intent()` — genera antes de pedir confirmación |

**Comportamiento:**

1. **Literal** — `"hola que tal?"` → se escribe tal cual.
2. **Especificación** — “programa python fibonacci recursivo” → una llamada al LLM genera código; warning `file_write_content_generated`.
3. **Código con fences** — se extrae el bloque, sin ```; si no hay extensión y es Python → `.py`.

---

## Servicios

| Servicio | Puerto | Estado final |
|----------|--------|----------------|
| llama.cpp | 8080 | **Detenido** |
| Cerebro | 7842 | **Detenido** |

---

## Pruebas live (`POST /api/query` + `tool-confirm`)

### 1 — Texto literal

**Prompt:** `crea un archivo smart_literal.txt con contenido "hola que tal?"`

**Warnings:** `file_write_fast_path`

**Contenido pendiente:** `hola que tal` (12 caracteres)

**Archivo en disco:** `~/Desktop/CerebroFiles/smart_literal.txt` → `hola que tal`

**Resultado:** PASS

---

### 2 — Descripción (Fibonacci recursivo)

**Prompt:** `crea un archivo pruebacodigo.txt con contenido de un programa python usando recursion para la secuencia de fibonacci`

**Warnings:** `file_write_content_generated`, `file_write_fast_path`

**Contenido pendiente (extracto):**

```python
def fibonacci(n):
    if n <= 1:
        return n
    else:
        return fibonacci(n - 1) + fibonacci(n - 2)
# ... ejemplo de uso con input ...
```

**Nota UI:** “(Contenido generado a partir de tu descripción.)”

**Archivo en disco:** `~/Desktop/CerebroFiles/pruebacodigo.txt` — código Fibonacci real (368 bytes), **no** la frase descriptiva.

**Resultado:** PASS

---

### 3 — Bloque markdown en el prompt

**Prompt:** `crea un archivo pruebacodigo2 con contenido ```python def fibonacci(n): ... ````

**Warnings:** `file_write_fast_path` (sin LLM extra — fences extraídos localmente)

**Archivo:** `pruebacodigo2.py` (extensión inferida)

**Contenido en disco:**

```python
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1)+fibonacci(n-2)
```

Sin delimitadores ` ```python `.

**Resultado:** PASS

---

## Resumen

| # | Caso | LLM generación | Extensión | Veredicto |
|---|------|----------------|-----------|-----------|
| 1 | Literal | No | `.txt` | PASS |
| 2 | Spec Fibonacci | Sí | `.txt` (nombre pedido) | PASS |
| 3 | Fences en prompt | No | `.py` inferida | PASS |

---

## Relacionado

- `manual_tests/file_write_fast_path_e2e_2026-05-24.md` — fast path básico (confirmación)
- `manual_tests/frontend_chat_qwen3_2026-05-24.md` — sesión manual original
