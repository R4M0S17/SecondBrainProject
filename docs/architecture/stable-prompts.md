# Stable prompts — regresión de fast paths

Lista de frases **validadas en frontend** (y/o E2E) que deben seguir funcionando.  
Cualquier cambio en fast paths, runtime o heurísticas de parse debe pasar estos casos.

Relacionado: [`fast-paths.md`](fast-paths.md) · [`fast-path-evolution-plan.md`](fast-path-evolution-plan.md)

---

## Cómo usar este documento

| Momento | Acción |
|---------|--------|
| Antes de merge | Correr tests unitarios equivalentes (Fase 2: `make test-stable`) |
| Después de cambio en runtime | Probar manualmente los prompts marcados **UI** en el chat |
| Nueva feature estable | Añadir fila aquí + test en `stable_fast_path_prompts.yaml` (Fase 2) |

**Leyenda**

- **Fast path:** handler que gana (ver orden en `fast-paths.md`).
- **Source:** `literal` \| `fenced` \| `spec` (solo file write).
- **LLM:** si hace falta llamada extra para generar cuerpo del archivo.
- **Confirm:** si el usuario debe aprobar `write_file` en UI.

---

## File write — contenido literal

| Prompt | Fast path | Source | LLM | Confirm | Resultado esperado |
|--------|-----------|--------|-----|---------|-------------------|
| `crea un archivo ejemplo.txt con contenido Hola, mundo!` | file_write | literal | No | Sí | Archivo con `Hola, mundo` |
| `crea un archivo nota_escritorio_cerebro.txt con el contenido de "hola desde escritorio cerebro"` | file_write | literal | No | Sí | Escrito en `~/Desktop/CerebroFiles/` |
| `Write a file called test-cerebro.txt with the word hello` | file_write | literal | No | Sí | Contenido `hello` |

---

## File write — spec + generación LLM

| Prompt | Fast path | Source | LLM | Confirm | Resultado esperado |
|--------|-----------|--------|-----|---------|-------------------|
| `crea un archivo pruebapython.txt con un a funcion con recursion de la sisecion de fibonacci` | file_write | spec | Sí | Sí | Código Python con `fibonacci`; **no** volcar código entero al chat sin pending_tool |
| `crea un archivo recetaprueba.txt en donde escribes una receta pequeña para cocinar panqueques` | file_write | spec | Sí | Sí | Receta completa en archivo (~900+ bytes); UI: 0.0s + 1 TOOL |
| `crea un archivo recetaprueba2.txt en donde escribes una receta pequeña para cocinar crepes` | file_write | spec | Sí | Sí | Receta de crepes en archivo |
| `crea un archivo truthtable.txt con una tabla de la verdad para matematica discreta` | file_write | spec | Sí | Sí | Tabla con filas/columnas; **no** solo la frase del prompt |
| `crea un archivo truthtable.txt en donde escribas una tabla de la verdad para matematica discreta` | file_write | spec | Sí | Sí | Igual; spec sin prefijo `en donde escribas` |
| `crea un archivo juegos.txt con 3 videojuegos de playstation` | file_write | spec | Sí | Sí | Lista de 3 títulos reales; **no** solo `3 videojuegos de playstation` |
| `crea un archivo “prueba.txt” con solamente 3 nombres de mujer inventados` | file_write | spec | Sí | Sí | Tres nombres en archivo; comillas tipográficas en filename OK |

**must_not_contain** (regresión crítica):

- No escribir literalmente: `en donde escribas una tabla de la verdad…`
- No escribir literalmente: `3 videojuegos de playstation` como único contenido
- No responder solo en chat cuando el intent es file write (salvo error de generación)

---

## File write — calendario fusion

| Prompt | Fast path | Source | LLM | Confirm | Resultado esperado |
|--------|-----------|--------|-----|---------|-------------------|
| `crea un archivo calendarioprueba2.txt con los 2 proximos cumpleaños en mi calendario` | file_write + calendar_fusion | literal (body from calendar) | No | Sí | Archivo con líneas de cumpleaños; UI: 0.0s + 1 TOOL |
| `crea un archivo pruebacalendario.txt con contenido de los proximos 3 cumpleaños en mi calendario` | file_write + calendar_fusion | spec → calendar | No | Sí | Cuerpo desde calendario, nota “Contenido obtenido del calendario” |
| `crea un archivo calendarioprueba.txt con los 3 proximos cumpleaños en mi calendario` | file_write + calendar_fusion | — | No | Sí | Sin keyword `contenido` en prompt |

**Prioridad:** estos prompts **no** deben caer en calendar read (paso 4); deben encolar `write_file`.

---

## File write — código con fences

| Prompt | Fast path | Source | LLM | Confirm | Resultado esperado |
|--------|-----------|--------|-----|---------|-------------------|
| `crea un archivo pruebacodigo2 con contenido ```python\ndef fibonacci(n): ...``` | file_write | fenced | No | Sí | `.py` sugerido; código sin fences en disco |

---

## Calendar read (sin archivo)

| Prompt | Fast path | LLM | Confirm | Resultado esperado |
|--------|-----------|-----|---------|-------------------|
| `¿qué tengo en el calendario mañana?` | calendar_read | No | No | Texto de eventos en chat |
| `próximo evento en mi calendario` | calendar_read | No | No | Un evento o “sin eventos” |
| `cuántos eventos tengo esta semana` | calendar_read | No | No | Respuesta numérica / listado |

**No** debe crear archivo ni `pending_tool write_file`.

---

## File search (sin escritura)

| Prompt | Fast path | LLM | Confirm | Resultado esperado |
|--------|-----------|-----|---------|-------------------|
| `busca el archivo demo.txt` | file_search | No | No | Rutas encontradas o mensaje claro |
| `crea un archivo demo.txt con hola` | file_write (not file_search) | — | Sí | File search **no** debe interceptar |

---

## Math

| Prompt | Fast path | Resultado esperado |
|--------|-----------|-------------------|
| `17 × 23` | math | `391` (o resultado correcto) |
| `What is (2+3)*4?` | math o LLM | Preferible math si expresión pura |

---

## Checklist manual UI (post-cambio)

Ejecutar en el chat del frontend con backend + llama.cpp activos:

- [ ] Cumpleaños → archivo (fusion)
- [ ] Receta panqueques / crepes
- [ ] Tabla de verdad (con y sin “en donde escribas”)
- [ ] 3 videojuegos PlayStation
- [ ] 3 nombres inventados con `“prueba.txt”`
- [ ] Fibonacci sin palabra “contenido”
- [ ] Pregunta calendario sin crear archivo

Reportes E2E: `manual_tests/e2e/file_write_spec_heuristics_2026-05-26.md`, `manual_tests/e2e/calendar_file_export_fusion_2026-05-25.md`.
