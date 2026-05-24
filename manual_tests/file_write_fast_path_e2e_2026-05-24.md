# Live E2E — File write fast path (2026-05-24)

Manual backend test after implementing Problem A fixes (`file_write_fast_path.py`, `write_file` result messages).

**Environment:** macOS, 8 GB RAM, local llama.cpp + Cerebro FastAPI  
**Branch context:** `fix-1-ram-containment` (file-write fast path merged in `core/agents/`)

---

## Services

| Service | Command | Port | Status after test |
|---------|---------|------|-------------------|
| llama.cpp chat | `make engine` | 8080 | Stopped |
| Cerebro backend | `make run` | 7842 | Stopped |

**Engine model:** `Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf` (symlinked from `cerebro/bin/models/` into `bin/models/` because default `chat.args` path was missing at repo root).

**Backend status at start:** `engine_ok: true`, `provider: llamacpp`, `ram_pressure: warn` (~6.78 / 8 GB used).

**Write folder:** `~/Desktop/CerebroFiles` (`CEREBRO_FILES_PATH` default).

---

## Test prompts

### Test 1 — Spanish fast-path (explicit create)

**Prompt:**
```text
crea un archivo ejemplo.txt con contenido Hola desde backend manual
```

**Agent:** `general-v1`

**Response (before approve):**
```text
Necesito tu aprobación para ejecutar `write_file`. Aprueba o rechaza la acción en el panel de confirmación.

Archivo: `ejemplo.txt`
Ruta: `/Users/mb/Desktop/CerebroFiles/ejemplo.txt`
Contenido (25 caracteres): Hola desde backend manual
```

**Metadata:**
- `warnings`: `ram_pressure_warn`, `file_write_fast_path`
- `pending_tool`:
  ```json
  {
    "name": "write_file",
    "args": {
      "path": "/Users/mb/Desktop/CerebroFiles/ejemplo.txt",
      "content": "Hola desde backend manual"
    }
  }
  ```

**After `POST /api/tool-confirm` (`approve`):**
```text
Herramienta `write_file` ejecutada:
Archivo escrito en: /Users/mb/Desktop/CerebroFiles/ejemplo.txt (25 bytes)
```

**File on disk:** `~/Desktop/CerebroFiles/ejemplo.txt` → `Hola desde backend manual`  
**Result:** PASS

---

### Test 2 — English fast-path

**Prompt:**
```text
Write a file called test-cerebro.txt with the word hello
```

**Response (before approve):** Confirmation message with path `/Users/mb/Desktop/CerebroFiles/test-cerebro.txt`, content `hello`.

**Metadata:** `file_write_fast_path` in warnings; `pending_tool` with correct path and content.

**After approve:**
```text
Archivo escrito en: /Users/mb/Desktop/CerebroFiles/test-cerebro.txt (5 bytes)
```

**File on disk:** `~/Desktop/CerebroFiles/test-cerebro.txt` → `hello`  
**Result:** PASS

---

### Test 3 — Explicit write_file path (diagnosis P0 prompt)

**Prompt:**
```text
Usa write_file para crear /Users/mb/Desktop/CerebroFiles/manual-test-e2e.txt con contenido E2E OK
```

**Response (before approve):** Confirmation with path `/Users/mb/Desktop/CerebroFiles/manual-test-e2e.txt`, content `E2E OK`.

**After approve:**
```text
Archivo escrito en: /Users/mb/Desktop/CerebroFiles/manual-test-e2e.txt (6 bytes)
```

**File on disk:** `~/Desktop/CerebroFiles/manual-test-e2e.txt` → `E2E OK`  
**Result:** PASS

---

### Test 4 — Vague Spanish (edge case)

**Prompt:**
```text
Crea un archivo de texto de ejemplo en mi carpeta permitida con un saludo corto
```

**Observation:** Fast path matched incorrectly (no LLM call, ~0 s latency):
- Parsed filename: `de`
- Path: `/Users/mb/Desktop/CerebroFiles/de`
- Content: `de ejemplo en mi carpeta permitida con un saludo corto`

**Result:** FAIL (regex too greedy on “archivo **de** texto…”). File was removed after test. Prefer explicit prompts from Tests 1–3.

---

## Summary

| Test | Prompt style | Fast path | Confirm required | File created | Verdict |
|------|----------------|-----------|------------------|--------------|---------|
| 1 | Spanish explicit | Yes | Yes | `ejemplo.txt` | PASS |
| 2 | English explicit | Yes | Yes | `test-cerebro.txt` | PASS |
| 3 | Explicit path + write_file | Yes | Yes | `manual-test-e2e.txt` | PASS |
| 4 | Vague Spanish | Yes (misfire) | Yes | `de` (wrong) | FAIL |

**Fix validated for Problem A (diagnosis):** Explicit create-file prompts no longer hallucinate “file created” without `write_file`; user sees path + must approve before write.

---

## Disk state after Tests 1–3

```
~/Desktop/CerebroFiles/
  ejemplo.txt           (25 bytes)  Hola desde backend manual
  test-cerebro.txt      (5 bytes)   hello
  manual-test-e2e.txt   (6 bytes)   E2E OK
```

---

## API flow used

1. `POST /api/query` with `question` + `agent: general-v1`
2. If `metadata.pending_tool.name == "write_file"` → `POST /api/tool-confirm` with `decision: "approve"`
3. Verify file exists at `pending_tool.args.path`

---

## Related docs

- [`diagnosis_frontend_chat_qwen3_2026-05-21.md`](diagnosis_frontend_chat_qwen3_2026-05-21.md) — Problem A (hallucinated file creates)
- [`FIX_TEST2.md`](FIX_TEST2.md) — H3.3 file-write micro-route
- Automated tests: `tests/test_file_write_fast_path.py`

---

## Shutdown

After testing, processes on ports **8080** (llama-server) and **7842** (Cerebro) were killed.
