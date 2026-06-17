#!/bin/bash
set -e

echo "=== Cerebro Native Setup ==="

if [ "$(uname)" != "Darwin" ]; then
    echo "Este script es solo para macOS. Usa 'docker compose up' en otras plataformas."
    exit 1
fi

if ! command -v brew &>/dev/null; then
    echo "Instalando Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

echo "Instalando dependencias del sistema..."
brew install llama.cpp python@3.11 node 2>/dev/null || brew upgrade llama.cpp python@3.11 node

if ! command -v rustc &>/dev/null; then
    echo "Instalando Rust..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
fi

echo "Configurando entorno Python..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"

echo "Descargando modelos..."
bash scripts/download-models.sh

echo "Construyendo frontend..."
cd ui/tray
npm install
npm run build
cd ../..

echo ""
echo "=== Instalacion completa ==="
echo ""
echo "Para arrancar:"
echo "  Terminal 1: make engine       # llama.cpp con Metal GPU"
echo "  Terminal 2: make run          # FastAPI en :7842"
echo ""
echo "O abre http://localhost:7842 en tu navegador."
