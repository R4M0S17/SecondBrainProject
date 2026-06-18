# File search — acceso a `~/Desktop` (fast path + tools)

**Fecha:** 2026-05-26

## Objetivo
Que el buscador pueda encontrar archivos en `~/Desktop` **por defecto**:

- Fast path determinista (`file_search_fast_path.py`)
- Camino con herramientas (`search_files` del runtime)

## Cambios aplicados
1. `authorized_read_paths()` (fast path) ahora incluye `~/Desktop` como raíz de lectura por defecto:
   - `core/agents/file_search_fast_path.py`
   - `cerebro/core/agents/file_search_fast_path.py`
2. `AUTHORIZED_READ_PATHS` (runtime con tools) ahora incluye `~/Desktop` en los entrypoints:
   - `main.py`
   - `cerebro/main.py`

3. Smoke test live con llama.cpp actualizado para crear el probe en `~/Desktop` y llamar al fast path **sin** forzar `CEREBRO_AUTHORIZED_READ_PATHS`:
   - `scripts/test_file_search_llamacpp.py`

## Pruebas realizadas

### Unit tests (backend)
```bash
.venv/bin/pytest -q tests/test_filesystem_tools.py tests/test_file_search_fast_path.py
```
Resultado: `28 passed`

### Live smoke con llama.cpp (stack readiness)
```bash
.venv/bin/python scripts/test_file_search_llamacpp.py
```
Resultado esperado:
- inicia llama.cpp engine si no está arriba,
- el fast path encuentra el archivo probe en `~/Desktop`,
- al final se detiene llama-server y se libera el puerto `8080`.

## Nota de seguridad
El test live borra el archivo probe al terminar (best-effort). El apagado se hace con `pkill -f llama-server`, así que si hay otra sesión de llama-server propia corriendo, puede verse afectada.

