# Unificación `cerebro/` → `core/`

## Problema

El proyecto tenía dos copias del backend:

| Path | Estado |
|---|---|
| `core/` | ✅ Trackeado en git — fuente de verdad |
| `cerebro/core/` | 🚫 En `.gitignore` — copia divergente |

`cerebro/` era una copia completa del repo en la raíz, pero el **launcher desktop** (`~/.cerebro/desktop.json`) apuntaba a `cerebro/` como `cerebro_root`. Esto causaba que:

- Editar `core/` no afectaba al runtime (el launcher ejecutaba `cerebro/main.py`)
- `cerebro/core/` tenía archivos que `core/` no tenía (y viceversa)
- Confusión: "edito algo pero no funciona, actualicé el que no era"

## Cambios realizados

### 1. Migración de archivos (2026-06-10)

| Archivo | De `cerebro/core/` | A `core/` | Estado |
|---|---|---|---|
| `tools/handlers/search.py` | ✅ Existía | ✅ Migrado | Declarado en perfiles, sin registro |
| `agents/kernel.py` | ✅ Existía | ✅ Migrado | No usado por `main.py` |
| `agents/profiles/` | ✅ Existía | ✅ Migrado | Directorio vacío |
| `pipeline/` (7 stages) | ✅ Existía | ✅ Migrado | No usado por `main.py` |
| `tools/audit.py` | ✅ Existía | ✅ Migrado | Solo usado por `pipeline/` |
| `inference/local_embedding_provider.py` | ✅ Mal ubicado | ❌ No migrado | Es duplicado de `providers/local_embedding_provider.py` |

Ninguno de estos archivos afecta al runtime actual. Se migraron para no perder trabajo experimental.

### 2. `~/.cerebro/desktop.json`

**Antes:**
```json
"cerebro_root": "/Users/mb/Desktop/Javier/SecondBrain/cerebro"
```

**Después:**
```json
"cerebro_root": "/Users/mb/Desktop/Javier/SecondBrain"
```

Ahora el launcher desktop ejecuta `main.py` de la raíz → importa `core/` de verdad.

### 3. `Makefile` (raíz)

**Antes:**
```makefile
desktop-icon desktop-app desktop-install:
	$(MAKE) -C cerebro $@
```

**Después:** Los targets ahora trabajan directamente con `ui/tray/` (que ya existe en la raíz).

### 4. `.pre-commit-config.yaml`

Se eliminó `exclude: ^cerebro/` del hook de mypy (ya no hay directorio `cerebro/`).

### 5. `AGENTS.md`

Se actualizó la referencia a la copia `cerebro/` para indicar que fue eliminada.

## Estructura final

```
SecondBrain/
├── core/           ← Único backend (FastAPI). Editar aquí.
├── ui/tray/        ← Frontend React/Tauri.
├── main.py         ← Entry point.
├── config/
│   ├── chat.args
│   └── profiles/
├── bin/
│   └── start_engine.sh
├── tests/
└── docs/
    └── UNIFICACION_CEREBRO.md  ← Este archivo
```

## Verificación

```bash
make test-stable   # 152/153 tests OK (1 preexistente falla de cumpleaños)
make lint          # black + ruff + mypy
```

El launcher desktop ahora apunta a la raíz. Para regenerar la config:

```bash
make desktop-config   # desde la raíz
```

Para lanzar:

```bash
make run             # desde terminal
# o
make desktop-launch  # desde el icono desktop
```
