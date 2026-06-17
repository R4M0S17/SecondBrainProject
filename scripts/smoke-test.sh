#!/bin/bash
set -e

MODE=${1:-docker}

if [ "$MODE" = "docker" ]; then
    echo "=== Smoke test: Docker ==="
    docker compose build --quiet
    docker compose up -d
    echo "Waiting for backend (30s)..."
    sleep 30
    echo "Checking /api/health..."
    curl -sf http://localhost:7842/api/health | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('status')=='ok'; print('OK')"
    echo "Checking frontend serves..."
    curl -sf http://localhost:7842 | python3 -c "import sys; assert b'doctype' in sys.stdin.buffer.read(); print('OK')"
    echo "Checking query endpoint..."
    curl -sf -X POST http://localhost:7842/api/query \
      -H "Content-Type: application/json" \
      -d '{"message": "Que hora es?"}' | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'response' in d; print('OK')"
    docker compose down
    echo "=== Docker smoke test PASSED ==="

elif [ "$MODE" = "native" ]; then
    echo "=== Smoke test: Native ==="
    if [ "$(uname)" != "Darwin" ]; then
        echo "Native smoke test requires macOS"
        exit 1
    fi
    echo "Starting engine..."
    make engine &
    ENGINE_PID=$!
    sleep 8
    echo "Starting backend..."
    make run &
    BACKEND_PID=$!
    sleep 12
    echo "Checking /api/health..."
    curl -sf http://localhost:7842/api/health | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('status')=='ok'; print('OK')"
    kill $ENGINE_PID $BACKEND_PID 2>/dev/null || true
    echo "=== Native smoke test PASSED ==="

else
    echo "Usage: $0 [docker|native]"
    exit 1
fi
