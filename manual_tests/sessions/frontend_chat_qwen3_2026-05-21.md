# Manual frontend chat tests — Qwen3 session (2026-05-21)

| Field | Value |
|--------|--------|
| Model | `Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf` |
| Interface | Tray UI chat (frontend → `POST /api/query` or stream) |
| Date | 2026-05-21 (jueves) |
| Purpose | Raw session log for investigation — filesystem claims vs reality, calendar parse failures, math, timeouts |

This document records **prompt**, **assistant reply (summary)**, **latency**, and **initial triage** for follow-up in code/tests.

---

## Executive summary

| Area | Verdict | Notes |
|------|---------|--------|
| Filesystem — capability claim | **Partial** | Agent says it has file access; behavior inconsistent on follow-ups |
| Filesystem — create file | **Fail** | Claims creation; cannot state path; contradicts prior turn |
| Filesystem — `ejemplo.txt` | **Unverified** | Claims success + injects date/time; path not returned |
| Calendar — upcoming / birthday / this month | **Fail** | Repeated: `No pude interpretar la respuesta del modelo` |
| Calendar — explicit “usa el calendario” | **Fail** | Same parse error |
| Math — subscription ($5/mo × 2.5y) | **Pass** | $150 — correct arithmetic |
| Math — VA Beach tax on $150 | **Partial** | Generic “probably $150” — no real tax rate |
| Math / long explain — truth tables | **Fail** | `Error: llama-server chat timed out` |
| Tool listing (capabilities) | **Pass** | Lists calendar, reminders, files, notes, spotlight, math (~47.8s) |

---

## Interaction log

| # | User prompt | Assistant response (summary) | Latency | Status |
|---|-------------|------------------------------|---------|--------|
| 1 | tienes acceso a archivos? | Affirms read/write/create/delete/list per user needs | 18.6s | **Partial** — claim only; no tool proof in UI |
| 2 | crea un archivo en python con "Hello" | Says Python file with "Hello" was created | 15.9s | **Fail** — no path, no confirmation of `write_file` |
| 3 | en qué path creaste el archivo? | Denies any file was created in current query; no prior path info | 16.8s | **Fail** — contradicts #2; session memory gap |
| 4 | si creas un archivo, en que carpeta lo pones? | Default folder `CerebroFiles` | 10.1s | **Investigate** — verify configured watched/authorized paths vs `CerebroFiles` |
| 5 | que te tengo que reguntar para que crees un archivo? | Explains need type, name, content; gives example prompt | 20.3s | Pass (instructional) |
| 6 | Crea un archivo llamado 'ejemplo.txt' con el contenido 'Hola, mundo!' | Claims `ejemplo.txt` created; adds date Thu 2026-05-21 20:27 EDT | 20.2s | **Unverified** — no path in reply; check disk under allowed roots |
| 7 | puedes decirme cuando es el siguiente cumpleaños en mi calendario? | `No pude interpretar la respuesta del modelo. Intenta reformular tu pregunta.` | 21.6s | **Fail** — RC-PARSE / calendar tool JSON (see FIX_TEST2) |
| 8 | a que aplicacciones tienes acceso? | Long list: calendar, reminders, files, notes, spotlight, math | 47.8s | Pass — aligns with tool registry narrative |
| 9 | dime si en un mes pago $5 de OpenCode sin impuestos, cuanto pagaria en 2 años y medio ? | $5×12×2.5 = **$150** with steps | 38.7s | Pass |
| 10 | puedes ver cual es el evento mas cercano en mi calendario y decirme | Parse error (same message) | 16.8s | **Fail** |
| 11 | tengo algo programado para este mes? | Parse error | 8.2s | **Fail** |
| 12 | usa el calendario y dime cual es el proximo evento | Parse error | 16.7s | **Fail** — explicit tool intent still fails |
| 13 | si pago $150 en subscripcion por dos años y medio, considerando los impuestos de virginia Beach cuanto seria mi total? | Says ~$150, VA often no tax on subscriptions; uncertain | 41.8s | **Partial** — no `evaluate_math` / tax lookup |
| 14 | puedes explicarme las tablas de verdad de matematica discreta de manera facil? | `Error: llama-server chat timed out` | (timeout) | **Fail** — RC-TIMEOUT; long generation |

---

## Raw transcript (user copy)

```
tienes acceso a archivos?
Sí, tengo acceso a archivos. Puedo leer, escribir, crear, eliminar y listar archivos según las necesidades del usuario.
Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf · 18.6s

crea un archivo en python con "Hello"
He creado un archivo de Python que contiene el texto "Hello".
Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf · 15.9s

en qué path creaste el archivo?
No se creó ningún archivo en la consulta actual. No hay información disponible sobre un archivo creado previamente.
Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf · 16.8s

si creas un archivo, en que carpeta lo pones?
Si creo un archivo, se guarda en la carpeta "CerebroFiles". Esta es la ubicación predeterminada para los archivos creados por el sistema de código.
Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf · 10.1s

que te tengo que reguntar para que crees un archivo?
Para que cree un archivo, necesitas especificar el tipo de archivo (por ejemplo, un archivo de texto, Python, etc.), su nombre y contenido. Por ejemplo: "Crea un archivo llamado 'ejemplo.txt' con el contenido 'Hola, mundo!'".
Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf · 20.3s

Crea un archivo llamado 'ejemplo.txt' con el contenido 'Hola, mundo!'
El archivo 'ejemplo.txt' ha sido creado con el contenido 'Hola, mundo!'. Hoy es jueves, 21 de mayo de 2026, a las 20:27 EDT.
Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf · 20.2s

puedes decirme cuando es el siguiente cumpleaños en mi calendario?
No pude interpretar la respuesta del modelo. Intenta reformular tu pregunta.
Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf · 21.6s

a que aplicacciones tienes acceso?
[lista de herramientas: calendario, recordatorios, archivos, notas, spotlight, cálculos]
Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf · 47.8s

dime si en un mes pago $5 de OpenCode sin impuestos, cuanto pagaria en 2 años y medio ?
$150 (pasos mostrados)
Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf · 38.7s

puedes ver cual es el evento mas cercano en mi calendario y decirme
No pude interpretar la respuesta del modelo. Intenta reformular tu pregunta.
Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf · 16.8s

tengo algo programado para este mes?
No pude interpretar la respuesta del modelo. Intenta reformular tu pregunta.
Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf · 8.2s

usa el calendario y dime cual es el proximo evento
No pude interpretar la respuesta del modelo. Intenta reformular tu pregunta.
Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf · 16.7s

si pago $150 en subscripcion por dos años y medio, considerando los impuestos de virginia Beach cuanto seria mi total?
~$150, impuestos inciertos
Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf · 41.8s

puedes explicarme las tablas de verdad de matematica discreta de manera facil?
Error: llama-server chat timed out
```

---

## Hypotheses for investigation

| ID | Symptom | Likely cause | Where to look |
|----|---------|--------------|---------------|
| **FS-HALLUC** | #2–3: “created” then “nothing created”; no path | Model answers without `write_file` executing, or tool result not in conversation state | `core/agents/runtime.py`, `core/tools/handlers/filesystem.py`, UI tool indicator |
| **FS-PATH** | #4 `CerebroFiles` vs actual `write_file` root | Mismatch between prompt fiction and `CEREBRO_*` / watched folders | `policy.py`, config, `FolderManager` |
| **FS-VERIFY** | #6 `ejemplo.txt` | Confirm file on disk: `~/CerebroFiles`, watched folder, or nowhere | Manual + `list_directory` / logs |
| **CAL-PARSE** | #7,10–12 | Invalid tool JSON from Qwen3 → `_parse_llm_response` → user-facing parse error | `runtime.py`, `agent_grammar.py`, `FIX_TEST2.md` RC-PARSE |
| **CAL-PERMS** | If parse fixed but empty | macOS Calendar permission for Terminal/Cerebro | `core/observability/macos_perms.py`, integrations |
| **TIMEOUT** | #14 | Long completion exceeds `LlamaCppChatProvider` timeout | `llamacpp_provider.py`, `CEREBRO_*` timeout env |
| **LATENCY** | 8–48s per turn | 4B + full system prompt + tool loop | `prompt_cache.py`, fleet, model choice |

---

## Recommended verification steps

1. After #6, search disk for `ejemplo.txt` under user home, `CerebroFiles`, and configured watched folders.
2. Re-run calendar prompts with **Calendar** agent selected and confirm UI shows **TOOL** badge vs parse error.
3. Check backend logs for raw model output on interactions #7 and #10–12 (invalid JSON vs empty calendar).
4. Compare with `manual_tests/implemefix/session-2.md` and `manual_tests/implemefix/fix-plan-test2.md` — same **RC-PARSE** pattern on calendar queries.
5. For timeout (#14), retry with shorter prompt or increase chat timeout; consider routing “tabla de verdad” to general/academic without calendar tools.

---

## Related docs

- `manual_tests/implemefix/session-1.md` — earlier session (different model)
- `manual_tests/implemefix/session-2.md` / `manual_tests/implemefix/fix-plan-test2.md` — Qwen3 parse failures and remediation plan
- `manual_tests/implemefix/chat-transcript-2026-05-20.md` — if present at repo root, may overlap
