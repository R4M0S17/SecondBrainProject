# Cerebro — Cómo Arrancar

Elige un backend de inferencia y sigue las instrucciones correspondientes.

---

## Opción A — llama.cpp (recomendado, más rápido en M1)

Necesitas **3 terminales**. Arranca en este orden.

### Fix único (solo la primera vez)

```bash
sed -i '' 's/^--flash-attn$/--flash-attn on/' \
  /Users/mb/Desktop/Javier/SecondBrain/cerebro/config/chat.args \
  /Users/mb/Desktop/Javier/SecondBrain/cerebro/config/coding.args \
  /Users/mb/Desktop/Javier/SecondBrain/cerebro/config/deep.args
```

### Terminal 1 — Motor llama.cpp (arrancar primero)

```bash
cd /Users/mb/Desktop/Javier/SecondBrain/cerebro
make engine
```

Espera hasta ver `llama server listening`. Déjala corriendo.

| Comando | Ideal para | RAM |
|---------|-----------|-----|
| `make engine` | Chat, preguntas rápidas | ctx 2048, mínima |
| `make engine-code` | Código (cierra Chrome antes) | ctx 8192 |
| `make engine-deep` | Documentos, RAG, resúmenes | ctx 6144 |

### Terminal 2 — Backend Cerebro

```bash
cd /Users/mb/Desktop/Javier/SecondBrain/cerebro
source .venv/bin/activate
CEREBRO_INFERENCE_BACKEND=llamacpp make run
```

### Terminal 3 — Frontend

```bash
cd /Users/mb/Desktop/Javier/SecondBrain/cerebro/ui/tray

# Modo dev (browser, hot reload)
npm run dev

# App de escritorio nativa
npx tauri dev
```

### Health check

```bash
curl http://localhost:7842/status
# Busca: "provider": "llamacpp"
```

### Solución de problemas

| Problema | Solución |
|---------|---------|
| `make engine` falla con `--flash-attn` | Ejecuta el fix de arriba (una sola vez) |
| Cerebro dice "connection error" | llama-server no está corriendo, arranca Terminal 1 primero |
| Respuestas muy lentas | Cierra Chrome, usa `make engine` |
| Mac se congela 2-3s al parar el motor | Normal, macOS liberando RAM |

---

## Tests

```bash
cd /Users/mb/Desktop/Javier/SecondBrain/cerebro
make test
# 337+ tests deben pasar. No requieren llama-server (usan mocks).
```
