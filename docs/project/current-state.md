# Cerebro — Estado Actual del Programa

> Última actualización: 2026-05-07

---

## Qué hace hoy

Cerebro es una aplicación de escritorio local (macOS) compuesta por un backend Python y una interfaz gráfica. Corre completamente en tu máquina, sin nube.

---

## Backend (Python · FastAPI · puerto 7842)

Servidor que arranca con `make run` y expone las siguientes capacidades:

### Chat con IA
- Recibe preguntas y devuelve respuestas en streaming token a token.
- Usa Ollama como motor de inferencia. Modelos instalados: `phi4-mini:latest` y `qwen3:4b`.
- Selecciona el modelo según RAM disponible (umbral mínimo: 0.3 GB libre).

### Agentes especializados
Cuatro perfiles de agente que el usuario puede elegir desde la UI:

| Agente | ID interno | Propósito |
|--------|-----------|-----------|
| General | `general-v1` | Asistente de propósito general |
| Thesis | `academic-v1` | Escritura académica e investigación |
| Code | `code-v1` | Programación y depuración |
| Calendar | `calendar-v1` | Agenda y recordatorios |

### Memoria
- **Corto plazo:** historial de la sesión activa (últimos mensajes).
- **Largo plazo:** base de datos vectorial (LanceDB + embeddings `nomic-embed-text`). Permite recuperar contexto relevante de conversaciones pasadas.
- **Conversaciones persistentes:** cada conversación se guarda en disco (`~/.cerebro/state/conversations/`) y se puede consultar desde el historial.

### Indexación de archivos
- El usuario define carpetas a observar desde la UI.
- El backend indexa los archivos en la base vectorial para que la IA pueda responder preguntas sobre ellos.
- Se puede consultar el progreso del indexado en tiempo real.

### Herramientas del agente Calendar
- `get_upcoming_events` — devuelve eventos próximos del calendario.
- `query_events` — busca eventos por palabra clave.

### Configuración y estado
- `GET/PATCH /api/config` — modelo activo, carpetas vigiladas, permisos de herramientas, modo no molestar.
- `GET /api/status` — métricas en vivo: RAM, latencia, total de consultas, modelo activo.
- `GET /api/models` — lista los modelos instalados en Ollama con su tamaño.

---

## Frontend (React + Tauri · UI de bandeja)

Interfaz de escritorio que arranca con `npm run dev` (modo dev) o como app empaquetada.

### Chat
- Caja de texto para enviar mensajes.
- Las respuestas aparecen token a token (streaming real).
- Muestra el modelo usado y la latencia de cada respuesta.
- Soporte de cancelación de respuesta en curso.

### Selector de agente
- Dropdown para cambiar entre los 4 agentes sin reiniciar nada.

### Panel de configuración (Settings)
- **Model:** lista los modelos instalados en Ollama en tiempo real. Sección separada de modelos recomendados no instalados (con instrucción de `ollama pull`).
- **Carpetas vigiladas:** agregar/quitar carpetas para indexación.
- **Permisos de herramientas:** activar/desactivar ejecución de Python, escritura de archivos, lectura, búsqueda web.
- **No molestar:** silenciar notificaciones proactivas.

### Historial de conversaciones
- Panel lateral con lista de todas las conversaciones pasadas.
- Vista detallada de cada conversación con todos sus mensajes.

### Barra de estado
- Se actualiza cada 10 segundos con: RAM usada/disponible, modelo activo, latencia promedio y p95, total de consultas.

### Wizard de primer arranque
- Detecta si Ollama está corriendo.
- Verifica si los modelos están descargados.
- Pide al usuario que configure sus carpetas vigiladas.
- Solo se muestra una vez; persiste el estado en `~/.cerebro/state/wizard.json`.

---

## Lo que aún NO está terminado

| Función | Estado |
|---------|--------|
| Tool confirmation (aprobar/denegar herramientas desde la UI) | Parcial |
| Observador de archivos automático (watchdog en tiempo real) | No implementado |
| Monitoreo proactivo (notificaciones por calendario/contexto) | No implementado |
| Autenticación / acceso remoto | No implementado (planeado) |
| Ejecución de Python en sandbox | Infraestructura lista, no conectada a la UI |

---

## Stack técnico resumido

| Capa | Tecnología |
|------|-----------|
| Inferencia | Ollama (`phi4-mini:latest`, `qwen3:4b`) |
| Embeddings | `nomic-embed-text` vía Ollama |
| Base vectorial | LanceDB (disco local `~/.cerebro/db`) |
| Orquestación | LangGraph |
| Backend API | FastAPI + uvicorn (puerto 7842) |
| Frontend | React + Zustand + Tailwind + Vite |
| App de escritorio | Tauri |
