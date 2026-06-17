# Native macOS Setup Guide

Run Cerebro with full GPU acceleration, Apple Calendar integration, AppleScript automation, and the Tauri desktop app.

## Why Native?

| Feature | Native | Docker |
|---------|--------|--------|
| Metal GPU inference (25-35 t/s) | ✅ | ❌ (CPU 3-8 t/s) |
| Apple Calendar | ✅ | ❌ |
| AppleScript / Automation | ✅ | ❌ |
| Tauri desktop app | ✅ | ❌ |
| RAM efficiency | ✅ (~2.5 GB) | ❌ (~4.5 GB + VM) |

## Prerequisites

- macOS (Apple Silicon or Intel)
- 8 GB+ RAM (16 GB recommended)
- ~2 GB free disk for model

## One-Command Setup

```bash
git clone https://github.com/your-org/cerebro.git
cd cerebro
make setup
```

This will automatically:
1. Install Homebrew (if missing)
2. Install llama.cpp, Python 3.11, Node.js, Rust
3. Create a Python virtualenv and install dependencies
4. Download the GGUF model to `bin/models/`
5. Build the React frontend to `ui/tray/dist/`

## Running

### Development Mode (3 terminals)

```bash
# Terminal 1: Start the inference engine
make engine

# Terminal 2: Start the backend
make run

# Terminal 3: Start the frontend dev server (with HMR)
cd ui/tray && npm run dev
```

Open **http://localhost:1420** (Vite dev) or **http://localhost:7842** (served from backend if dist/ exists).

### Production Desktop App

```bash
cd ui/tray
npm run tauri:build:release
cp -R src-tauri/target/release/bundle/macos/Cerebro.app /Applications/
```

### 8 GB Mac Profile

```bash
make lite
```
This disables MLX, ContextEnricher, and uses local embeddings to save RAM.

## Common Tasks

```bash
make setup           # One-time: install everything
make engine          # Start llama.cpp with Metal GPU
make run             # Start FastAPI backend on :7842
make test            # Run all tests with coverage
make test-stable     # Fast-path regression suite
make lint            # Black + Ruff + Mypy
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `make engine` fails: port 8080 in use | `kill $(lsof -t -i :8080)` then retry |
| `make engine` fails: model not found | Download model: `bash scripts/download-models.sh` |
| `make run` fails: port 7842 in use | `kill $(lsof -t -i :7842)` or set `CEREBRO_PORT=7843` |
| `make setup` fails on brew install | Run `brew update && brew upgrade` then retry |
| Frontend shows blank page | Build the frontend: `cd ui/tray && npm run build` |
| Calendar not working | Grant Calendar permission in System Settings → Privacy & Security |
| Python dependency errors | `source .venv/bin/activate && pip install -e ".[dev]"` |
| Tauri build fails | Ensure Xcode CLI tools: `xcode-select --install` |
