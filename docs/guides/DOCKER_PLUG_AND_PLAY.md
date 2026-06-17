# Docker Plug-and-Play Guide

Run Cerebro anywhere with Docker — no Python, Node, or macOS required.

## Requirements

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) 4.x+
- 8 GB RAM minimum (16 GB recommended)
- ~2 GB free disk for model download

## Quick Start

```bash
git clone https://github.com/your-org/cerebro.git
cd cerebro
docker compose up
```

Open **http://localhost:7842** in your browser.

## First Run

On first launch, `docker compose up` will:
1. Build the backend container (Node → Python multi-stage)
2. Pull the `ghcr.io/ggerganov/llama.cpp:server` image
3. Download the GGUF model (~1.9 GB from HuggingFace)
4. Start llama.cpp (CPU mode) + backend + frontend

This takes **3-10 minutes** depending on your connection and CPU.

## Commands

```bash
docker compose up -d            # Background mode
docker compose logs -f backend  # Watch backend logs
docker compose logs -f llamacpp # Watch inference logs
docker compose down             # Stop everything
docker compose down -v          # Stop + delete persistent data
docker compose build --no-cache backend  # Rebuild without cache
```

## Performance Notes

### CPU Threads

llama.cpp defaults to `--threads 4` in the compose file. Adjust to half your host's physical cores:

```yaml
command: >
  --model /models/Qwen3.5-2B-UD-Q4_K_XL.gguf
  --threads 8   # ← for a 16-core machine
```

### M1 8GB Warning

Docker Desktop runs a Linux VM consuming ~1.5 GB before any services start. Total RAM usage:

| Component | RAM |
|-----------|-----|
| Docker Desktop VM | ~1.5 GB |
| llama.cpp (CPU, 2B Q4) | ~2.5 GB |
| Backend + embeddings | ~500 MB |
| **Total** | **~4.5 GB** |
| Remaining for macOS | ~3.5 GB |

On 8 GB machines this causes swapping. Use **native mode** on macOS for best performance.

### Tokens/s Comparison

| Mode | Tokens/s | CPU |
|------|----------|-----|
| Native M1 + Metal | 25-35 t/s | ~5% |
| Docker M1 (CPU) | 3-8 t/s | ~80-100% |
| Docker Linux (CPU) | 5-12 t/s | ~60-80% |

Docker is suitable for testing and simple queries. For conversation-heavy use, run natively on macOS.

## Changing the Model

1. Place your `.gguf` file in `bin/models/`
2. Update `docker-compose.yml`:
   ```yaml
   environment:
     - CEREBRO_LLAMACPP_MODEL=your-model.gguf
   ```
3. Update the `command:` in the llamacpp service to match
4. Rebuild: `docker compose up -d`

## GPU Acceleration (Linux/NVIDIA)

For NVIDIA GPU passthrough on Linux, add to `docker-compose.yml`:

```yaml
services:
  llamacpp:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

And change `--n-gpu-layers 0` to `--n-gpu-layers 99` (or your model's layer count).

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `port 7842 already in use` | Kill existing process or change `CEREBRO_PORT` |
| Model download fails | Check `docker compose logs backend` for the error; download manually from HuggingFace |
| llama.cpp won't start | Check logs: `docker compose logs llamacpp`. The GGUF may be corrupted |
| Backend crashes on startup | Ensure `config/settings.toml` has valid `base_url = "http://llamacpp:8080"` or override via env |
| Frontend shows blank page | The `dist/` build may have failed. Check `docker compose logs backend` for StaticFiles warnings |
