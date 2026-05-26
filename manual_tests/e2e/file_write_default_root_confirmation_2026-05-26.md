# File write — default root + confirmation path (desktop/llama smoke)

**Fecha:** 2026-05-26

## Objetivo

1. Asegurar que si el usuario pide **crear un archivo** sin especificar un path, el backend lo escriba en **`CerebroFiles`** (ruta autorizada por defecto).
2. Hacer que el **modal de confirmación** muestre **la ruta destino** (`toolPath`) donde se creará el archivo, para que el usuario confirme “dónde” se escribe.

## Cambios realizados

### Backend: `write_file` soporta rutas relativas

Archivos:
- `core/tools/handlers/filesystem.py`
- `cerebro/core/tools/handlers/filesystem.py`

Cambio:
- Si `write_file(path=...)` recibe un `path` **no absoluto** (ej. `"nota.txt"`), se mapea a:
  - `authorized_paths[0] / <nombre>`
- Esto restaura el comportamiento “si no das path, escribimos en CerebroFiles”, incluso cuando el modelo emite herramientas con rutas relativas.

### Frontend: modal muestra la ruta destino

Archivo:
- `ui/tray/src/components/chat/InputArea.tsx`

Cambio:
- Cuando `metadata.pending_tool` llega con `args.path`, ahora se pasa como `pendingConfirmation.toolPath`.
- El `ConfirmModal` ya soporta renderizar la fila “Path” cuando `toolPath` existe.

## Pruebas

### Unit tests backend

```bash
.venv/bin/pytest -q tests/test_filesystem_tools.py tests/test_file_write_fast_path.py
```

Resultado: **31 passed**

### Live smoke con llama.cpp (y apagado al final)

Archivo:
- `scripts/test_file_write_llamacpp.py`

Qué valida:
- El runtime usa llama.cpp para generar contenido en los casos `spec`/`fenced`.
- Luego ejecuta el handler `write_file` y verifica:
  - El archivo se crea en el root autorizado.
  - También prueba un caso adicional de path **relativo** para asegurar el mapeo al root autorizado.

Command:

```bash
.venv/bin/python scripts/test_file_write_llamacpp.py
```

Resultado:
- `OK runtime [literal/spec/fenced]`
- `Stopping llama-server…`
- `llama.cpp stopped (port 8080 free)`

## Nota

Si ves que el modelo dice “archivo creado” pero el archivo no aparece en disco:
- ahora el modal de confirmación muestra la ruta exacta donde se escribirá;
- aun así la escritura final depende del flujo `pending_tool` + `tool-confirm`.

