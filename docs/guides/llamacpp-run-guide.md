
## Cómo ejecutar el sistema

### Paso 1 — Elige un perfil e inicia el motor

Abre una terminal en la carpeta `cerebro/` y ejecuta uno de estos comandos según la tarea:

```bash
# Para conversación rápida (ctx 2048, RAM mínima)
make engine

# Para análisis de código (ctx 8192, máxima inteligencia — cierra Chrome antes)
make engine-code

# Para documentos y RAG (ctx 6144, equilibrio)
make engine-deep
```

El servidor queda escuchando en `http://127.0.0.1:8080`. Déjalo corriendo en esa terminal.

### Paso 2 — Inicia Cerebro con el backend llama.cpp

En una segunda terminal, desde `cerebro/`:

```bash
CEREBRO_INFERENCE_BACKEND=llamacpp make run
```

Cerebro arrancará en `http://localhost:7842` usando llama-server como motor principal y Ollama como fallback para embeddings.

### Paso 3 (opcional) — Cambiar perfil en caliente

Para cambiar el perfil sin reiniciar Cerebro, detén el motor (Ctrl+C en la primera terminal) y lanza otro:

```bash
make engine-code   # o engine, o engine-deep
```

El backend llama-server se reinicia con el nuevo contexto. Cerebro detecta la reconexión automáticamente.

---

### Referencia rápida de perfiles

| Comando | Contexto | KV Cache | Temperatura | Ideal para |
|---|---|---|---|---|
| `make engine` | 2048 tokens | q4_0 | 0.7 | Chat, preguntas rápidas |
| `make engine-code` | 8192 tokens | q8_0 | 0.2 | Análisis de código, revisiones |
| `make engine-deep` | 6144 tokens | q8_0 | 0.3 | Documentos, RAG, resúmenes |

### Solución de problemas

**El servidor no arranca** → Verifica que `llama-server` esté en PATH: `which llama-server`

**Mac se congela al cambiar perfil** → Es normal durante 2-3 segundos mientras macOS libera RAM. El `--mlock` previene esto en sesiones largas pero no durante el apagado del proceso.

**Cerebro responde con error de conexión** → llama-server no está corriendo. Ejecuta `make engine` primero.

**Respuestas muy lentas** → Cierra otras aplicaciones (especialmente Chrome) y usa `make engine` en lugar de `make engine-code`.