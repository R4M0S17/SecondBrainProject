> **Status: ARCHIVADO — quizás más adelante**  
> Plan vigente: [`CURRENT_FOCUS.md`](../CURRENT_FOCUS.md) · Índice: [`maybe-later/README.md`](README.md)


# Plan: Plug-and-Play para Cerebro (Dual-mode)

**Meta**: Que cualquier persona pueda correr Cerebro con **un solo comando**, en cualquier plataforma.

**Estrategia dual**:
- **Docker** → sandbox cross-platform (Linux/Windows/demo). Funciona en todos lados, sin GPU, sin integraciones nativas.
- **Script nativo** → experiencia premium en macOS. Metal GPU, Apple Calendar, AppleScript, Tauri, 0% CPU en inferencia.

Ambos modos comparten el mismo `docker compose up` o `bash scripts/setup.sh` como entrypoint único.

---

## Índice

1. [M0 — Modelos con URLs reales](#m0--preliminar-dependencias-y-urls-de-modelos)
2. [M1 — Servir frontend desde FastAPI](#m1--servir-frontend-desde-fastapi)
3. [M2 — Dockerfile del backend](#m2--dockerfile-del-backend)
4. [M3 — llama.cpp en Docker](#m3--entrada-para-llamacpp)
5. [M4 — Docker Compose](#m4--docker-compose)
6. [M5 — Entrypoint y modelo download](#m5--entrypoint-y-modelo-download)
7. [M6 — Ajustes al backend](#m6--ajustes-al-backend-para-docker)
8. [M7 — Setup script nativo macOS](#m7--setup-script-nativo-macos)
9. [M8 — README y docs](#m8--readme-y-documentación)
10. [M9 — Testing](#m9--testing-y-validación)
11. [M10 — Edge cases](#m10--edge-cases-y-limitaciones)

---

## M0 — Preliminar: dependencias y URLs de modelos

### 0.1 Elegir modelos con URLs reales en HuggingFace

Actualmente `config/settings.toml` y `config/profiles/lite-8gb.env` referencian:
- `Qwen3.5-2B-UD-Q4_K_XL.gguf` (chat)
- `v5-nano-retrieval-Q4_K_M.gguf` (embeddings)
- `mlx-community/Qwen3.5-2B-MLX-4bit` (MLX, no aplica en Docker)

**Acción**: Verificar que estos modelos existen en HuggingFace con URLs descargables públicas.

✅ **Verificado**:

| Modelo | Repo HF | URL |
|--------|---------|-----|
| `Qwen3.5-2B-UD-Q4_K_XL.gguf` | [`unsloth/Qwen3.5-2B-GGUF`](https://huggingface.co/unsloth/Qwen3.5-2B-GGUF) | `https://huggingface.co/unsloth/Qwen3.5-2B-GGUF/resolve/main/Qwen3.5-2B-UD-Q4_K_XL.gguf` |
| `v5-nano-retrieval-Q4_K_M.gguf` | [`jinaai/jina-embeddings-v5-text-nano-retrieval-GGUF`](https://huggingface.co/jinaai/jina-embeddings-v5-text-nano-retrieval-GGUF) | `https://huggingface.co/jinaai/jina-embeddings-v5-text-nano-retrieval-GGUF/resolve/main/v5-nano-retrieval-Q4_K_M.gguf` |

Ambos retornan 302 (redirect a descarga S3) — confirmado que existen y son públicos. ✅

El script `scripts/download-models.sh` usa estas URLs reales. El modelo de embeddings solo se descarga si `CEREBRO_EMBEDDINGS_BACKEND=llamacpp` (en Docker el default es `local`, no se necesita).

### 0.2 Actualizar `.env.example` ✅ Implementado

### 0.2 Actualizar `.env.example`

Agregar variables para ambos modos:
```env
# ── Docker ──
# CEREBRO_LLAMACPP_URL=http://llamacpp:8080
# CEREBRO_FRONTEND_DIR=/app/ui/tray/dist

# ── Modo sandbox (desactiva features macOS) ──
# CEREBRO_MODE=sandbox

# ── Nativo (default) ──
# CEREBRO_LLAMACPP_URL=http://127.0.0.1:8080
```

### 0.3 Verificar compatibilidad del frontend

El `dist/index.html` usa assets con rutas absolutas (`/assets/index-*.js`), lo que es compatible con `StaticFiles(directory=..., html=True)` montado en `/`. Confirmado.

---

## M1 — Servir frontend desde FastAPI

### 1.1 Agregar `StaticFiles` mount en `ui/tray/server.py`

**Archivo**: `ui/tray/server.py` (después del último `app.include_router`, línea ~2061)

```python
from fastapi.staticfiles import StaticFiles

_frontend_dir = os.getenv("CEREBRO_FRONTEND_DIR", "")
if not _frontend_dir:
    _frontend_dir = str(Path(__file__).resolve().parent / "dist")
if Path(_frontend_dir).exists():
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")
else:
    logger.warning("Frontend dist not found at {}. API-only mode.", _frontend_dir)
```

> **Nota**: El código real usa `loguru.logger` (ya importado como `logger` en server.py), no `logging.getLogger`. El import de `Path` ya existe (línea 25). El import de `StaticFiles` se agregó en las importaciones de FastAPI.

**Consideraciones**:
- Se monta al **final** para que los routers `/api/*` tengan prioridad
- `html=True` hace que rutas como `/settings` sirvan `index.html` (SPA fallback)
- En modo nativo, si no existe `dist/`, simplemente no se monta (no rompe)
- El warning permite debug rápido: si alguien abre `http://localhost:7842` y ve 404, sabe por qué

### 1.2 Verificar que no rompe el modo Tauri nativo

Tauri carga `dist/index.html` desde archivo local. El mount no afecta. Probar con `make run` + abrir navegador.

---

## M2 — Dockerfile del backend

### 2.1 Multi-stage: Node build + Python runtime

```dockerfile
# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app
COPY ui/tray/package*.json ./
RUN npm ci
COPY ui/tray/ ./
RUN npm run build

# Stage 2: Python backend
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

COPY core/ core/
COPY main.py .
COPY config/ config/
COPY bin/start_engine.sh bin/
COPY scripts/download-models.sh /scripts/download-models.sh
RUN chmod +x /scripts/download-models.sh
COPY --from=frontend-builder /app/dist/ ui/tray/dist/

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV CEREBRO_FRONTEND_DIR=/app/ui/tray/dist
ENV CEREBRO_MODE=sandbox
EXPOSE 7842

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "main.py"]
```

### 2.2 `.dockerignore`

```
.git/
.venv/
__pycache__/
.mypy_cache/
.pytest_cache/
.ruff_cache/
node_modules/
ui/tray/node_modules/
ui/tray/src-tauri/
.DS_Store
*.md
docs/
tests/
manual_tests/
```

---

## M3 — Entrada para llama.cpp

### 3.1 Usar imagen oficial

`ghcr.io/ggerganov/llama.cpp:server` — soporta CPU y CUDA (Linux).

⚠️ **En macOS**: Esta imagen corre bajo la VM de Docker Desktop (Linux arm64), sin acceso a Metal. La inferencia será 100% CPU. Para GPU nativa, usar modo nativo.

### 3.2 Script `scripts/download-models.sh` (compartido Docker + nativo)

```bash
#!/bin/bash
set -e
MODELS_DIR=${MODELS_DIR:-/models}
CHAT_MODEL=${CEREBRO_LLAMACPP_MODEL:-Qwen3.5-2B-UD-Q4_K_XL.gguf}
EMBED_MODEL=${CEREBRO_EMBED_MODEL:-v5-nano-retrieval-Q4_K_M.gguf}

declare -A MODEL_URLS
MODEL_URLS["Qwen3.5-2B-UD-Q4_K_XL.gguf"]="${HF_BASE:-https://huggingface.co}/unsloth/Qwen3.5-2B-GGUF/resolve/main/Qwen3.5-2B-UD-Q4_K_XL.gguf"
MODEL_URLS["v5-nano-retrieval-Q4_K_M.gguf"]="${HF_BASE:-https://huggingface.co}/jinaai/jina-embeddings-v5-text-nano-retrieval-GGUF/resolve/main/v5-nano-retrieval-Q4_K_M.gguf"

download_if_missing() {
  local filename="$1"
  local url="${MODEL_URLS[$filename]}"
  [ -z "$url" ] && { echo "WARN: No URL for $filename"; return; }
  [ -f "${MODELS_DIR}/${filename}" ] && { echo "$filename exists"; return; }
  echo "Downloading $filename ($url)..."
  curl -L --retry 3 --retry-delay 5 -o "${MODELS_DIR}/${filename}" "$url"
}

download_if_missing "$CHAT_MODEL"

if [ "${CEREBRO_EMBEDDINGS_BACKEND:-local}" = "llamacpp" ]; then
  download_if_missing "$EMBED_MODEL"
fi
```

> **Nota**: El modelo de embeddings solo se descarga si `CEREBRO_EMBEDDINGS_BACKEND=llamacpp`. En Docker el default es `local` (sentence-transformers in-process), así que no se descarga innecesariamente. ✅ Implementado en `scripts/download-models.sh`.

### 3.3 Entrypoint `docker/entrypoint.sh` ✅ Implementado

```bash
#!/bin/bash
set -e

if [ -f /scripts/download-models.sh ]; then
    /scripts/download-models.sh
fi

mkdir -p ~/.cerebro/db ~/.cerebro/state ~/.cerebro/models

exec "$@"
```

---

## M4 — Docker Compose ✅ Implementado

### 4.1 `docker-compose.yml`

```yaml
services:
  llamacpp:
    image: ghcr.io/ggerganov/llama.cpp:server
    container_name: cerebro-llamacpp
    platform: linux/arm64
    volumes:
      - ./bin/models:/models:ro
    ports:
      - "8080:8080"
    command: >
      --model /models/Qwen3.5-2B-UD-Q4_K_XL.gguf
      --port 8080
      --ctx-size 4096
      --n-gpu-layers 0
      --host 0.0.0.0
      --threads 4
    deploy:
      resources:
        limits:
          cpus: "4"
          memory: "2g"
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8080/health"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  backend:
    build:
      context: .
      dockerfile: docker/Dockerfile
    container_name: cerebro-backend
    platform: linux/arm64
    ports:
      - "7842:7842"
    volumes:
      - cerebro_data:/root/.cerebro
      - ./bin/models:/models:ro
      - ./config:/app/config:ro
    depends_on:
      llamacpp:
        condition: service_healthy
    environment:
      - CEREBRO_LLAMACPP_URL=http://llamacpp:8080
      - CEREBRO_LLAMACPP_MODEL=Qwen3.5-2B-UD-Q4_K_XL.gguf
      - CEREBRO_EMBEDDINGS_BACKEND=local
      - CEREBRO_PORT=7842
      - CEREBRO_DB=/root/.cerebro/db
      - CEREBRO_STATE=/root/.cerebro/state
      - CEREBRO_SCHEDULER_ENABLED=false
      - CEREBRO_MLX_ENABLED=false
      - CEREBRO_LLAMACPP_SIMPLE=true
      - CEREBRO_PROACTIVE_CONTEXT=false
      - CEREBRO_MODE=sandbox
    deploy:
      resources:
        limits:
          cpus: "2"
          memory: "1g"
    restart: unless-stopped

volumes:
  cerebro_data:
```

**Cambios clave frente a la versión anterior**:
- `platform: linux/arm64` explícito para evitar emulación x86 (Rosetta) en M1
- `deploy.resources.limits` en ambos servicios para evitar que CPU se sature
- `--threads 4` en llama.cpp para no acaparar todos los cores
- `CEREBRO_MODE=sandbox` para que el runtime desactive features macOS
- Memory limits: 2g para llama.cpp + 1g para backend = 3g total (+ VM ~1.5g = ~4.5g)
- `./bin/models:/models` en vez de volumen nombrado → si ya descargaste modelos con el script nativo, Docker los reusa sin descargar 2 GB otra vez

### 4.2 Perfil con GPU (Linux/NVIDIA)

Perfil opcional para usuarios Linux con GPU NVIDIA. En v1, documentar como milestone futuro.

---

## M5 — Entrypoint y modelo download ✅

### 5.1 `scripts/download-models.sh` ✅

Ver M3.2. Creado en `scripts/download-models.sh`. Contiene las URLs reales verificadas de HuggingFace.

### 5.2 `docker/entrypoint.sh` ✅

Ver M3.3. Creado en `docker/entrypoint.sh`.

---

## M6 — Ajustes al backend para Docker ✅ Implementado

### 6.1 Variable `CEREBRO_MODE`

**Archivos**: `core/feature_flags.py` (nuevo) + `main.py`

**`core/feature_flags.py`**:
```python
from __future__ import annotations
import os

CEREBRO_MODE = os.getenv("CEREBRO_MODE", "native")  # "native" | "sandbox"

def is_sandbox() -> bool:
    return CEREBRO_MODE == "sandbox"
```

**`main.py`** — gating en 2 puntos:

1. **Registro de tools** (línea ~504): En sandbox se omiten `register_calendar_tools`, `register_macos_tools` y `register_automation_tools`. Las tools de sistema de archivos, matemáticas y web siempre se registran.

2. **ContextEnricher** (línea ~546): `enabled=PROACTIVE_CONTEXT and not is_sandbox()` — en sandbox el enricher existe pero devuelve `""` siempre.

Cuando `CEREBRO_MODE=sandbox`:
- Calendar tools → no registradas (no aparecen en el tool list del LLM)
- macOS tools → no registradas
- Desktop automation → no registrada
- ContextEnricher → desactivado (enrich() devuelve "")
- Cualquier AppleScript/JXA → nunca se invoca (no hay tools que lo llamen)

> Las tools restantes (filesystem, math, web, search) son cross-platform y funcionan sin cambios.

### 6.2 URL de inferencia: service name ✅

El backend apunta a `http://llamacpp:8080` via env var. `settings.toml` tiene `http://127.0.0.1:8080` como default. La env var `CEREBRO_LLAMACPP_URL=http://llamacpp:8080` ya está configurada en `docker-compose.yml`. `LlamaCppChatProvider` respeta esta variable.

### 6.3 Persistencia de datos ✅

Volumen `cerebro_data` monta `~/.cerebro`. Contiene LanceDB + estado de agentes. Definido en `docker-compose.yml`.

---

## M7 — Setup script nativo macOS ✅ Implementado

Script todo-en-uno para macOS: instala dependencias, descarga modelos, construye frontend, arranca todo.

```bash
#!/bin/bash
set -e

echo "=== Cerebro Native Setup ==="

# 1. Verificar macOS
if [ "$(uname)" != "Darwin" ]; then
    echo "Este script es solo para macOS. Usa 'docker compose up' en otras plataformas."
    exit 1
fi

# 2. Verificar/instalar Homebrew
if ! command -v brew &>/dev/null; then
    echo "Instalando Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# 3. Dependencias del sistema
echo "Instalando dependencias del sistema..."
brew install llama.cpp python@3.11 node 2>/dev/null || brew upgrade llama.cpp python@3.11 node

# 4. Rust (para Tauri)
if ! command -v rustc &>/dev/null; then
    echo "Instalando Rust..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
fi

# 5. Python venv + deps
echo "Configurando entorno Python..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"

# 6. Modelos
echo "Descargando modelos..."
bash scripts/download-models.sh

# 7. Frontend
echo "Construyendo frontend..."
cd ui/tray
npm install
npm run build
cd ../..

# 8. Frontend Tauri (opcional)
read -p "¿Compilar app de escritorio Tauri? (requiere ~5 min) [y/N]: " BUILD_TAURI
if [ "$BUILD_TAURI" = "y" ] || [ "$BUILD_TAURI" = "Y" ]; then
    cd ui/tray
    npm run tauri:build:release
    cd ../..
    echo "App instalada en /Applications/Cerebro.app"
fi

echo ""
echo "=== Instalación completa ==="
echo ""
echo "Para arrancar:"
echo "  Terminal 1: make engine       # llama.cpp con Metal GPU"
echo "  Terminal 2: make run          # FastAPI en :7842"
echo ""
echo "O直接用 el launcher de escritorio si compilaste Tauri."
```

### 7.2 `make setup`

Agregar al Makefile:
```makefile
setup:
	bash scripts/setup.sh
```

Así el flujo nativo es: `make setup && make engine && make run`.

### 7.3 `scripts/download-models.sh` compartido

El setup nativo llama al mismo script que Docker. Models van a `bin/models/` — que es el mismo directorio que Docker monta como bind mount (`./bin/models:/models`). Esto evita descargas duplicadas: si ya corriste `make setup`, Docker encuentra los modelos en el host y no los descarga otra vez.

---

## M8 — README y documentación ✅ Implementado

### 8.1 README.md — Quick Start dual-mode

El README debe mostrar **dos caminos** desde el inicio:

````markdown
## Quick Start

Elige tu modo:

### 🐳 Docker (cualquier plataforma — CPU-only)

```bash
docker compose up
# Abrir http://localhost:7842
```

> Demo rápido, sin GPU, sin integraciones macOS.
> Para experiencia completa en Mac, usa el modo nativo.

### 🍎 Nativo macOS (recomendado — Metal GPU + Calendar + Tauri)

```bash
make setup && make engine && make run
# Abrir http://localhost:7842 (o usar la app Tauri)
```

> Inferencia con aceleración GPU, Apple Calendar, AppleScript,
> automatización de escritorio, y app de escritorio nativa.
````

### 8.2 Cheatsheet

```bash
# ── Docker ──
docker compose up -d            # Arrancar en background
docker compose logs -f backend  # Ver logs
docker compose down             # Detener

# ── Nativo ──
make setup                      # Una vez: instalar todo
make engine                     # llama.cpp + Metal GPU
make run                        # FastAPI :7842
cd ui/tray && npm run dev       # Frontend en :1420
```

### 8.3 `docs/guides/DOCKER_PLUG_AND_PLAY.md` ✅ Creado

Guía detallada con:
- Requisitos (Docker Desktop, 8 GB RAM mínimo recomendado, 16 GB ideal)
- **Advertencia para M1 8GB**: Docker Desktop VM consume ~1.5 GB extra. Si notas lentitud, usa modo nativo.
- Primer arranque (descarga de modelos ~2 GB, puede tomar varios minutos)
- **Optimización de CPU en Docker**: En entornos sin GPU, ajustar `--threads` en `command:` del servicio `llamacpp` a la mitad de los núcleos físicos del host (ej. M1 8 cores → `--threads 4`). Esto evita que la inferencia por CPU congele el sistema operativo anfitrión. El valor por defecto en el compose es `--threads 4`.
- Solución de problemas
- Cómo cambiar el modelo
- Perfil GPU para Linux

### 8.4 `docs/guides/NATIVE_SETUP.md` ✅ Creado

Guía detallada para macOS:
- Por qué nativo es mejor en Mac (Metal, Calendar, AppleScript)
- Requisitos paso a paso
- Solución de problemas comunes (puertos ocupados, modelos faltantes)
- Cómo compilar Tauri

---

## M9 — Testing y validación ✅ Implementado

### 9.1 Smoke test Docker

```bash
docker compose build --quiet
docker compose up -d
sleep 20
curl -s http://localhost:7842/api/health          # → {"status":"ok"}
curl -s http://localhost:7842 | grep -c "doctype" # → 1 (frontend sirve)
curl -s -X POST http://localhost:7842/api/query \
  -H "Content-Type: application/json" \
  -d '{"message": "¿Qué hora es?"}'
docker compose down
```

### 9.2 Smoke test nativo

```bash
make install  # o make setup si existe
make engine &
sleep 5
make run &
sleep 10
curl -s http://localhost:7842/api/health
# matar procesos
```

### 9.3 Prueba de persistencia

```bash
docker compose up -d
curl -X POST http://localhost:7842/api/query -H "Content-Type: application/json" \
  -d '{"message": "Mi nombre es TestUser"}'
docker compose down

docker compose up -d
curl -X POST http://localhost:7842/api/query -H "Content-Type: application/json" \
  -d '{"message": "¿Cómo me llamo?"}'
# Debe recordar "TestUser"
docker compose down
```

### 9.4 Regresión nativa

Verificar que `make install && make run && make test-stable` sigue verde después de los cambios (StaticFiles mount, CEREBRO_MODE).

---

## M10 — Edge cases y limitaciones ✅ Documentado

### 10.1 Lo que NO funciona en cada modo

| Feature | Nativo macOS | Docker |
|---------|:---:|:---:|
| Metal GPU inference | ✅ | ❌ (CPU-only) |
| Apple Calendar | ✅ | ❌ |
| AppleScript | ✅ | ❌ |
| Tauri desktop UI | ✅ | ❌ (solo web) |
| Desktop automation | ✅ | ❌ |
| File system watcher | ✅ | ⚠️ (limitado) |
| Linux | ❌ | ✅ |
| Windows | ❌ | ✅ |

### 10.2 Docker en M1 8GB — Análisis realista de RAM

El plan original decía "3-4 GB". El análisis real es peor:

| Componente | RAM |
|------------|:---:|
| Docker Desktop VM (Linux) | ~1.5 GB fijos |
| llama.cpp (CPU, modelo 2B Q4) | ~2.5 GB |
| Backend Python + embeddings | ~500 MB |
| **Total** | **~4.5 GB** |
| Disponible para macOS + browser | ~3.5 GB |

**Consecuencia**: En una M1 8GB, Docker pone el sistema al límite. Swapping masivo, throttling, batería.

**Solución**: Documentar claramente que Docker en M1 8GB no es óptimo. Recomendar modo nativo. Para Docker, recomendar 16 GB RAM.

### 10.3 Rendimiento: CPU vs Metal

| Escenario | Tokens/seg (aprox) | CPU usage |
|-----------|:---:|:---:|
| Nativo M1 + Metal | 25-35 t/s | ~5% |
| Docker M1 (CPU arm64) | 3-8 t/s | ~80-100% |
| Docker Linux (CPU x86) | 5-12 t/s | ~60-80% |

La diferencia es de **un orden de magnitud**. Docker es usable para queries simples, frustrante para conversaciones largas.

### 10.4 Tamaño de descarga

Modelos GGUF: ~1.5-2 GB. La primera ejecución descarga automáticamente.

### 10.5 Estrategia de versiones

```yaml
# docker-compose.yml con tag versionado
backend:
  image: ghcr.io/tu-org/cerebro:latest  # O tag semver
```

Para distribution: publicar imagen en GitHub Container Registry.

---

## Orden de implementación

```
M0  ✅ → M1  ✅ → M2  ✅ → M3  ✅ → M4  ✅ → M5  ✅ → M6  ✅
M7  ✅ → M8  ✅ → M9  ✅ → M10 ✅
```

**Todos los módulos implementados.**

---

## Resumen de archivos nuevos a crear

| Archivo | Propósito | Estado |
|---------|-----------|--------|
| Archivo | Propósito | Estado |
|---------|-----------|--------|
| `docker/Dockerfile` | Backend container | ✅ |
| `docker/entrypoint.sh` | Entrypoint para container | ✅ |
| `docker-compose.yml` | Orquestación | ✅ |
| `.dockerignore` | Excluir del build context | ✅ |
| `scripts/download-models.sh` | Download de GGUF (Docker + nativo) | ✅ |
| `core/feature_flags.py` | Flag `CEREBRO_MODE` centralizado | ✅ |
| `scripts/setup.sh` | Setup nativo macOS todo-en-uno | ✅ |
| `scripts/smoke-test.sh` | Smoke tests (Docker + native) | ✅ |
| `docs/guides/DOCKER_PLUG_AND_PLAY.md` | Guía Docker | ✅ |
| `docs/guides/NATIVE_SETUP.md` | Guía nativa macOS | ✅ |

## Resumen de archivos existentes a modificar

| Archivo | Cambio | Estado |
|---------|--------|--------|
| `ui/tray/server.py` | Agregar StaticFiles mount | ✅ |
| `main.py` | Gatear registros macOS + ContextEnricher via `is_sandbox()` | ✅ |
| `.env.example` | Agregar vars Docker + CEREBRO_MODE | ✅ |
| `Makefile` | Agregar target `setup` | ✅ |
| `README.md` | Reemplazar Quick Start con selector de modo | ✅ |
