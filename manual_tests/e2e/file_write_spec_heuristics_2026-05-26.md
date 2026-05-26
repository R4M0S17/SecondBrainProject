# File write — spec vs literal heuristics (2026-05-26)

## Symptom (frontend manual chat)

| Prompt | Result before fix |
|--------|-------------------|
| Cumpleaños / recetas | OK (calendar fusion or `receta` keyword → `spec` + LLM) |
| Tabla de verdad | File created with literal phrase *"en donde escribas una tabla…"* or short garbage |
| 3 videojuegos PlayStation | File contained only *"3 videojuegos de playstation"* |
| 3 nombres inventados (`“prueba.txt”`) | No file — answer only in chat (curly quotes broke parser) |

## Root cause

Fast path classifies captured text as:

- **`literal`** → written as-is to disk (no second LLM call)
- **`spec`** → `generate_file_content()` fills the file

Only phrases matching `_SPEC_HINT_RE` (e.g. `receta`, `fibonacci`, `cumple`) became `spec`.  
Phrases like *tabla de verdad*, *videojuegos*, *nombres inventados* stayed **`literal`**.

Also:

- `en donde escribas…` was stored verbatim when classified as literal.
- Curly quotes around filenames (`“prueba.txt”`) did not match `[_FILENAME]` patterns.

## Fix

`core/agents/file_write_fast_path.py` (mirrored in `cerebro/core/`):

1. **Looser Spanish create patterns** — `con` + optional `contenido`; body can be a description.
2. **Curly/ASCII quotes** on filenames.
3. **Richer spec detection**:
   - Keywords: tabla, verdad, videojuego, nombres, inventados, matemática, …
   - Prefixes: `en donde escribas`, `donde escribes` (stripped before generation)
   - Quantity phrases: `3 videojuegos`, `solamente 3 nombres`
   - Short directive phrases with `para` / `inventad` / `escrib`
4. **`_looks_like_finished_literal`** — only skip generation for real pasted content (multiline, truth-table rows, short comma lists), not recipe specs with commas.

`file_content_generator.py`: prompt hints for lists and truth tables.

## Tests

```bash
.venv/bin/python -m pytest -q tests/test_file_write_fast_path.py   # 24 passed
.venv/bin/python scripts/test_file_write_llamacpp.py               # live llama.cpp (optional)
```

## Expected frontend behavior after fix

1. User asks to create a file with a **description** (not exact text).
2. Chat shows **pending `write_file`** (or executes after confirm) with **generated** body.
3. File on disk contains real content (table rows, game titles, names), not the instruction sentence.
