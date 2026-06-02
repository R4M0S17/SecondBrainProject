# Cerebro (SecondBrain)

Local-first agentic personal OS — Python backend (FastAPI) + React/Tauri desktop UI.

## Quick start

```bash
make install
make engine    # llama.cpp on :8080
make run       # API on :7842
```

See **[`docs/guides/howToRun.md`](docs/guides/howToRun.md)** for full setup (8 GB Mac: [`docs/guides/8gb-mac-quickstart.md`](docs/guides/8gb-mac-quickstart.md)).

## Documentation

| What you need | Where to look |
|---------------|---------------|
| **Full index** | [`docs/README.md`](docs/README.md) |
| **Agent / dev reference** | [`CLAUDE.md`](CLAUDE.md) |
| **Architecture deep-dive** | [`docs/architecture/program-overview.md`](docs/architecture/program-overview.md) |
| **Stabilization & fix plans** | [`docs/plans/`](docs/plans/) |
| **Manual QA logs** | [`manual_tests/README.md`](manual_tests/README.md) |

## Repository layout

```
core/              Python backend
ui/tray/           React + Tauri frontend
docs/              Canonical documentation
manual_tests/      Manual E2E notes and smoke reports
config/            llama.cpp profiles and env templates
tests/             pytest (mocked inference)
```

## Modelos locales recomendados

El programa carga modelos GGUF desde el directorio `bin/models/`. Aquí los modelos relevantes y cómo descargarlos desde Hugging Face.

- CEREBRO_LLAMACPP_MODEL — modelo de chat (ej.: `Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf` o `llama-3.2-3b-instruct-q4_k_m.gguf`).
- CEREBRO_EMBED_MODEL — embeddings (ej.: `v5-nano-retrieval-Q4_K_M.gguf`).
- CEREBRO_ROUTER_MODEL — router ligero (ej.: `SmolLM2-135M-Instruct-Q4_K_M.gguf`).
- CEREBRO_GENERAL_MODEL — modelo general (ej.: `Llama-3.2-3B-Instruct-Q4_K_M.gguf`).
- CEREBRO_CODE_MODEL — modelo para código (ej.: `Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf`).

Ejemplos para descargar desde Hugging Face (reemplazar OWNER/MODEL y FILENAME):

Bash (requiere HF_TOKEN si el modelo está restringido):

```bash
mkdir -p bin/models
curl -L -H "Authorization: Bearer $HF_TOKEN" -o bin/models/llama-3.2-3b-instruct-q4_k_m.gguf \
  "https://huggingface.co/OWNER/MODEL/resolve/main/llama-3.2-3b-instruct-q4_k_m.gguf"
```

Usando huggingface_hub (Python):

```bash
pip install huggingface-hub
python - <<'PY'
import os
from huggingface_hub import hf_hub_download
hf_hub_download(repo_id="OWNER/MODEL", filename="llama-3.2-3b-instruct-q4_k_m.gguf", repo_type="model", token=os.environ.get("HF_TOKEN"))
PY
```

Luego exportar las variables de entorno que el proyecto usa, por ejemplo:

```bash
export CEREBRO_LLAMACPP_MODEL="llama-3.2-3b-instruct-q4_k_m.gguf"
export CEREBRO_EMBED_MODEL="v5-nano-retrieval-Q4_K_M.gguf"
```

Notas:
- Algunos modelos piden aceptación de licencia y requieren login en Hugging Face (usa `huggingface-cli login`).
- Para descargas repetidas o modelos grandes se recomienda usar `scripts/download_model.py` incluido en este repositorio o seguir `docs/testing/QUICK_START.md`.

