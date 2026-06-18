# Implementation Roadmap — Cerebro

Tasks planificadas, priorizadas y detalladas para implementación futura.

---

## Priority: High (near-term, high impact)

### H1. LoRA de Tool Calling para Qwen3.5-2B

**Problema:** El modelo base (incluso Qwen3.5-2B) no está optimizado para el formato de tool calling de Cerebro (`<tool_call><function=...>` XML). Esto causa errores de parsing, argumentos faltantes, y llamadas a herramientas incorrectas.

**Solución:** Entrenar un adaptador LoRA que especialice al Qwen3.5-2B en el tool calling de Cerebro.

**Dataset:**
- 500-1000 ejemplos de `(user_query, tool_call_xml)` extraídos de `tests/fixtures/stable_fast_path_prompts.yaml` y logs reales
- Cada ejemplo: prompt de usuario → respuesta con `<tool_call><function=name><parameter=key>value</parameter></function></tool_call>`
- Incluir 21 herramientas del registry: calendar, filesystem, macOS, math

**Entrenamiento (no local — usar Colab/cloud):**
```
Hardware: GPU T4 gratuita (Colab) o L4/L10 (~$0.50 USD)
Framework: LLaMA-Factory o Unsloth
Base: Qwen/Qwen3.5-2B (o Qwen_Qwen3.5-2B-Q4_K_M.gguf cuantizado)
Método: LoRA (rank=16, alpha=32, target_modules=[q_proj,k_proj,v_proj,o_proj])
Steps: 200-500
Tiempo estimado: 10-30 minutos en T4
```

**Post-entrenamiento:**
```
1. Exportar adaptador → .safetensors
2. Convertir a formato GGUF LoRA (llama.cpp compatible)
3. Cargar en inference con: --lora cerebro_tools.lora
4. Impacto en RAM: ~10-50 MB adicionales
```

**Beneficio esperado:**
- Tool calling preciso (>95% vs ~70-80% actual)
- Menos reintentos de herramientas
- Menos tokens gastados en errores de parsing
- Sin aumento de latencia (LoRA se fusiona en forward pass)

**Archivos a modificar:**
- `core/agents/runtime.py`: cargar LoRA en provider
- `core/inference/providers/llamacpp.py`: soporte para `--lora`
- `config/settings.toml`: ruta del adaptador LoRA

---

### H2. SmolLM2-135M Fine-tuned como Query Classifier

**Problema:** `SpecializedAgentRouter` usa heuristicas (prefix routing + keywords) y una llamada al LLM grande para clasificar queries. Las heuristicas son frágiles y la llamada al LLM grande es cara.

**Solución:** Fine-tune de SmolLM2-135M-Instruct como clasificador binario/multiclase de intenciones.

**Dataset (~1000 ejemplos):**
```
Categorías objetivo: calendar, code, files, general, reminder, math
Ejemplos:
  "agenda una reunion para mañana" → calendar
  "escribe un script de python" → code
  "busca el archivo reporte.pdf" → files
  "cuanto es 2+2" → math
  "recuerdame comprar leche" → reminder
  "como estas?" → general
```

**Entrenamiento (local o Colab):**
```
Hardware: M1 CPU o GPU T4 — cualquiera funciona, modelo tiny
Framework: transformers + peft (LoRA) o fine-tune full
Épocas: 5-10
Tiempo: ~5 minutos en M1, ~1 minuto en T4
Formato export: ONNX o llama.cpp GGUF
```

**Integración en Cerebro:**
```python
# core/agents/router.py
class SmolRouter:
    def __init__(self, model_path: str):
        self.model = llama_load(model_path)  # ~50 MB, <100 MB RSS
        self.labels = ["calendar", "code", "files", "general", "reminder", "math"]

    def classify(self, query: str) -> str:
        # Single forward pass, ~1-5ms
        logits = self.model.forward(query)
        return self.labels[logits.argmax()]
```

**Beneficio:**
- ~500 t/s (in-process, sin HTTP)
- ~50-100 MB RSS
- ~99% accuracy en las categorías entrenadas
- Elimina la llamada al LLM grande para clasificación
- Reemplaza heuristicas frágiles en `runtime.py`

---

### H3. Qwen3.5-0.8B como Worker Secundario (2B + 0.8B)

**Problema:** El 2B es single-threaded. Mientras genera una respuesta larga, otras queries se encolan.

**Solución:** Correr 2B (port 8080) + 0.8B (port 8081) simultáneamente. Router despacha queries simples al 0.8B.

**Arquitectura:**
```
Query → Router (SmolLM2) → ¿complejo? → 2B (port 8080)
                          → ¿simple?  → 0.8B (port 8081)
```

**Capacidad en M1 8GB:**
```
2B:  ~2.5 GB RSS
0.8B: ~0.9 GB RSS
SmolLM2: ~0.1 GB RSS
Total: ~3.5 GB → ~4.5 GB libres ✓
```

**Queries que maneja el 0.8B:**
- Fast path misses simples (hora, fecha, recordatorios)
- Tool calls triviales (leer archivo, crear evento)
- Preguntas directas de una línea
- Cualquier query clasificada como "general" con baja complejidad

**Queries que siempre van al 2B:**
- Multi-step reasoning
- Code generation
- RAG con contexto largo
- Planner / task decomposition

**Archivos a modificar:**
- `core/inference/registry.py`: registrar provider secundario
- `core/agents/runtime.py`: lógica de ruteo por complejidad
- `main.py`: lanzar segundo server en `_build_app_state()`

---

### H4. RAG Full-Doc con 0.8B

**Problema:** RAG actual chunktea documentos y hace top-k retrieval. Para docs largos, el chunking pierde referencias cruzadas.

**Solución:** Usar el 0.8B (262K contexto, 900 MB RSS) para leer documentos enteros y extraer información sin chunking.

**Flujo:**
```
1. Query llega al router
2. Router detecta: pregunta de extracción sobre documento conocido
3. Cargar documento completo en contexto del 0.8B
4. Prompt: "Answer ONLY based on the provided text. Be concise."
5. Respuesta directa sin chunking
```

**Trigger:** Queries que contienen "que dice sobre", "encuentra", "busca en el documento", "según el archivo"

**Fallback:** Si el documento excede 262K tokens o el 0.8B no produce respuesta coherente, degradar a RAG chunked con el 2B.

---

### H5. Knowledge Sync Agent — Conocimiento Actualizado vía Internet

**Problema:** El modelo local tiene knowledge cutoff fijo. No sabe de eventos recientes, lanzamientos, o noticias. No hay mecanismo para mantener su conocimiento fresco sin re-entrenar.

**Solución:** Sistema completo de sincronización online que corre en background cuando el sistema está idle. Pipeline de ingesta → filtro de señal → LiveKnowledgeStore → inyección en contexto.

**Componentes:**
- `core/knowledge/sync_agent.py`: KnowledgeSyncAgent con fuentes RSS, GitHub, web
- `core/knowledge/live_store.py`: LiveKnowledgeStore (tabla LanceDB separada, 2000 entradas max, evicción por score)
- `core/knowledge/fresh_compressor.py`: FreshContextCompressor (compresión 300→60 tokens por chunk)
- `core/knowledge/fresh_router.py`: FreshKnowledgePathRouter (slot al inicio del FastPathRouter)

**Filtro de 3 capas** (sin LLM): léxico → dedup semántico (MiniLM, cosine >0.92) → score de novedad

**Integración:** se inyecta en `ambient_context` del `_RunState`, justo después del fast path. No toca el grafo LangGraph.

**Detalle completo:** `docs/knowledge-sync-agent.md`

**Archivos a modificar:**
- `core/knowledge/` (5 archivos nuevos)
- `core/agents/fast_path_router.py`: FreshKnowledge al inicio del orden
- `core/agents/runtime.py`: inyectar ambient_context
- `core/memory/vector_store.py`: soporte int8 vectors
- `main.py`: wiring paso 7
- `config/settings.toml`: sección [knowledge]

---

### H6. Corrección de Lectura de Calendario (Event Recognition)

**Problema:** El módulo de calendario tiene problemas para reconocer eventos correctamente. Errores en parsing de fechas, eventos duplicados, o eventos que no se detectan.

**Solución:** Revisar y corregir `core/tools/calendar/` y los fast paths de calendario.

**Áreas a revisar:**
- `core/tools/calendar/read.py`: parsing de eventos desde Apple Calendar (AppleScript en macOS)
- `core/tools/calendar/search.py`: búsqueda por fecha, título, descripción
- `core/agents/fast_path_router.py`: calendar fast path order and logic
- Tests: `tests/test_calendar*.py` (8 archivos) — verificar cobertura

**Problemas conocidos:**
- AppleScript output parsing frágil (cambia con versiones de macOS)
- Eventos recurrentes no se expanden correctamente
- Timezone handling incorrecto
- Eventos sin título se saltan

**Archivos a modificar:**
- `core/tools/calendar/*.py`
- `core/agents/fast_path_router.py` (sección calendar)

---

### H6. Web Search — Mejora del Output

**Problema:** El output del web search llega crudo o mal formateado. URLs rotas, snippets truncados, sin estructura utilizable por el LLM.

**Solución:** Pipeline de post-procesamiento para web search.

**Mejoras:**
1. Parsear y limpiar snippets (quitar HTML crudo, caracteres especiales)
2. Extraer metadatos útiles: título, fecha, dominio, snippet limpio
3. Formatear como JSON estructurado para el LLM en lugar de texto plano
4. Cache de resultados para evitar búsquedas repetidas

**Archivos a modificar:**
- Buscar implementación de web search en `core/tools/` o `core/agents/`
- Agregar pipeline de formateo

---

### H7. Expansión de Fast Paths

**Problema:** El Fast Path Router (`core/agents/fast_path_router.py`) solo cubre: Time/Date → Config Read → URL Open → Math → File write → Reminder → Calendar read → Calendar write → File search. Muchas queries comunes podrían resolverse sin LLM.

**Fast paths a agregar:**
- **Weather**: consulta clima local (si hay API configurada)
- **Dictionary**: definiciones de palabras, sinónimos
- **Unit conversion**: temperatura, distancia, moneda
- **System info**: RAM, CPU, batería, uptime
- **Calculator**: operaciones aritméticas básicas (quizás ya cubierto por math)
- **Contacts**: búsqueda rápida en libreta de direcciones de macOS
- **Clipboard**: leer/escribir portapapeles

**Archivos a modificar:**
- `core/agents/fast_path_router.py`: agregar nuevos handlers en el orden canónico
- `core/agents/runtime.py`: si se requiere nuevo orden de evaluación
- `core/tools/`: nuevos tool modules

---

## Priority: Medium (valuable but not blocking)

### M1. Conversation Distillation con 0.8B

**Problema:** `ShortTermStore.distill_if_needed()` usa el LLM principal para resumir historial cuando se llena el contexto (75% de 35 mensajes). Esto interrumpe la conversación activa.

**Solución:** Routear la destilación al 0.8B como tarea asíncrona de fondo.

**Trigger:** `push_message()` → `distill_if_needed()` → si hay 0.8B registrado, usarlo.

**System prompt:**
```
Condensa la conversación en máximo 3 bullet points. 
Mantén: intención del usuario, decisiones tomadas, información clave. 
Omite: saludos, despedidas, repeticiones.
```

**Output esperado:** ~50-150 tokens, estructura concisa, sin thinking overhead.

---

### M2. Tool Call Fast Path con 0.8B

**Problema:** Tool calls triviales (get_time, list_files, read_calendar) pasan por el LLM grande.

**Solución:** El 0.8B tiene tool calling en su chat template (`<tool_call>` XML). Usarlo para tool calls simples.

**Condiciones para ruteo al 0.8B:**
- Query no requiere razonamiento multi-step
- Herramienta no requiere confirmación (no es execute_python, write_file, etc.)
- Herramienta tiene parámetros fijos y predecibles

**Beneficio:** Libera al 2B para tareas complejas. El 0.8B responde tool calls en ~1-2s.

---

### M3. Fine-tune de LoRA Tool Calling (0.8B variant)

Si el LoRA del 2B funciona bien, crear una versión para el 0.8B. El 0.8B con LoRA de tool calling podría manejar tool calls simples con alta precisión a 23.6 t/s y solo 900 MB RSS.

---

### M4. Resumen de Documentos / Texto Pegado

**Problema:** No hay forma de pegar un texto largo o subir un documento y recibir un resumen estructurado. El usuario tiene que escribir "resume esto" cada vez.

**Solución:** Detectar automáticamente cuando el input del usuario es un documento/texto largo y ofrecer resumen.

**Triggers:**
- Input >500 tokens → pregunta "¿Quieres un resumen de este texto?"
- Archivo arrastrado al chat → extraer texto y resumir
- URL detectada → extraer contenido y resumir

**Flujo de resumen:**
```
1. Usuario pega texto o sube archivo
2. Fast path detecta: "modo resumen"
3. Usar 2B (o 0.8B si está disponible) con prompt especializado:
   "Genera un resumen estructurado: puntos clave, conclusiones, datos relevantes"
4. Output formateado: bullet points + secciones
```

**Frontend:**
- Botón "Resumir" en la UI del chat (junto al input)
- Detección automática de texto largo (>500 tokens)
- Soporte para drag & drop de archivos .txt, .md, .pdf

**Archivos a modificar:**
- `core/agents/fast_path_router.py`: nuevo fast path "summarize"
- `core/tools/`: nueva herramienta summarizer
- `ui/tray/src/components/chat/`: botón de resumen, drag & drop

---

### M5. Windows Port (Cross-Platform)

**Problema:** Cerebro depende de APIs macOS: Apple Calendar (JXA/AppleScript), Apple Notes, Spotlight (mdfind), CGEventTap (Quartz), osascript, y rutas estilo Unix. No funciona en Windows.

**Solución:** Port completo documentado en `docs/windows-port.md`. 9 fases:

| Fase | Descripción | Archivos Clave |
|---|---|---|
| 0 | Infraestructura: pywin32, paths `%USERPROFILE%`, platform detection | `core/utils/paths.py`, `pyproject.toml` |
| 1 | Calendar: Outlook COM API + ICS fallback + Google Calendar API | `integrations/calendar_backends/outlook.py` |
| 2 | Apps: Replace Spotlight/Notes/Notifications con PowerShell | `integrations/windows_apps.py` |
| 3 | Automation: CGEventTap → `keyboard`+`mouse` hooks + PowerShell gen | `core/automation/recorder_windows.py` |
| 4 | Filesystem: `osascript` Trash → `send2trash` | `core/tools/handlers/filesystem.py` |
| 5 | Scripts: `.sh`→`.bat`/`.ps1`, `lsof`→`netstat`, `bash`→`cmd` | `bin/start_engine.bat`, launcher `.ps1` |
| 6 | Tauri: Rust conditional compilation, Windows resources, shortcut key | `tauri.conf.json`, `lib.rs`, `launcher.rs` |
| 7 | Config: Windows defaults (paths, hotkey, MLX disabled) | `config/settings.toml`, `main.py` |
| 8 | GPU: CUDA + DirectML detection | `core/inference/fleet/hardware_monitor.py` |
| 9 | Testing: Fixtures mockeadas, CI pipeline Windows | `tests/conftest_windows.py` |

**Esfuerzo:** ~12-15 días hábiles. **Dependencias:** pywin32, send2trash, keyboard, mouse.
**Archivos a crear:** ~12. **Archivos a modificar:** ~15.

---

### M6. Asignar Funciones a Botones del Frontend

**Problema:** Hay botones en la UI de Tauri que no están conectados a ninguna función del backend.

**Inventario de botones a revisar:**
- `ui/tray/src/components/` — revisar cada componente
- `ui/tray/src/stores/` — revisar stores para acciones no implementadas
- Botones comunes sin conectar: settings guardar, cancelar, nuevo chat, borrar conversación, exportar chat

**Acción:**
1. Mapear todos los botones en `ui/tray/src/`
2. Identificar cuáles no tienen handler o llaman a endpoints que no existen
3. Implementar endpoints faltantes en `ui/tray/server.py` (bajo `/api/`)
4. Conectar stores de Zustand a los endpoints

**Archivos a modificar:**
- `ui/tray/src/components/**/*.tsx`: conectar onClick handlers
- `ui/tray/src/stores/*.ts`: implementar acciones
- `ui/tray/server.py`: endpoints faltantes

---

### M7. Document Upload & Summarize (Backend)

Backend para soportar M4. Endpoints:
- `POST /api/summarize` — acepta texto o file_path, devuelve resumen
- `POST /api/upload` — sube archivo, lo guarda en `CEREBRO_FILES_PATH`, indexa en VectorStore

**Archivos a modificar:**
- `ui/tray/server.py`: nuevos endpoints
- `core/tools/summarizer.py`: lógica de resumen

---

## Priority: Low (exploratory, nice-to-have)

### L1. Sintetizador de Queries para Dataset de Tool Calling

Generar dataset sintético para el LoRA de tool calling. Usar el propio 2B para generar ejemplos `(query → tool_call)` a partir de las definiciones de herramientas existentes en `core/tools/`.

```
Para cada herramienta en core/tools/:
  1. Prompt al 2B: "Genera 10 queries de usuario que requieran esta herramienta"
  2. Para cada query, generar el tool_call XML correcto
  3. Validar contra PolicyEngine
  4. Guardar en dataset
```

Esto permite escalar el dataset a 5000+ ejemplos sin esfuerzo manual.

---

### L2. Warmup Automático de Ambos Modelos

Script que precarga ambos modelos (2B + 0.8B) al iniciar Cerebro para evitar cold starts. Ejecutar una query dummy a cada uno durante `_build_app_state()`.

---

### L3. Evaluación Continua de Clasificador

Pipeline que corre semanalmente el clasificador SmolLM2 contra un test set curado y reporta accuracy por categoría. Si baja de 95%, re-entrenar.

---

### L4. Actualización de Conocimiento del Modelo Local vía Internet (Idea)

**Problema:** El modelo local tiene un knowledge cutoff fijo (fecha de entrenamiento). No sabe nada posterior. Actualmente no hay mecanismo para actualizar su conocimiento sin re-entrenar.

**Idea:** Sistema que, cuando hay conexión a internet, actualiza selectivamente el conocimiento del modelo local.

**Enfoques posibles (explorar):**

1. **RAG增强 con fuentes web periódicas**
   - Crawler diario que descarga Wikipedia/noticias/dominios configurados
   - Genera embeddings y los almacena en VectorStore
   - El modelo consulta RAG automáticamente para preguntas factuales
   - Sin re-entrenamiento, solo actualización de la base vectorial

2. **Knowledge Graph local**
   - Mantener un grafo de conocimiento (hechos, relaciones) en SQLite/LanceDB
   - Actualizarlo periódicamente desde fuentes confiables (wiki, arxiv, news APIs)
   - El modelo consulta el grafo vía herramienta antes de responder

3. **LoRA intercambiables por dominio**
   - Múltiples adaptadores LoRA: `conocimiento_2025.lora`, `medicina.lora`, `legislacion.lora`
   - Descargarlos bajo demanda cuando se necesita un dominio específico
   - Cargar/descargar en caliente (llama.cpp soporta `--lora` en runtime)

4. **Fine-tune delta periódico**
   - Cada N días, si hay conexión, descargar un LoRA con "conocimiento nuevo"
   - Entrenado automáticamente en servidor cloud con datos frescos
   - Aplicar como capa sobre el modelo base

**Próximos pasos:** Investigar viabilidad técnica de cada enfoque. El más prometedor a corto plazo es (1) RAG + VectorStore, que ya está parcialmente implementado.

---

### L5. (reserved)

---

## Summary

| ID | Tarea | Prioridad | Esfuerzo | Impacto | Dependencias |
|---|---|---|---|---|---|---|
| H1 | LoRA Tool Calling Qwen3.5-2B | High | 2-3 días | Alto (tool calling >95%) | Dataset sintético, Colab |
| H2 | SmolLM2-135M Classifier | High | 1-2 días | Alto (clasificación ~99%) | Dataset etiquetado |
| H3 | 0.8B Secondary Worker | High | 2-3 días | Alto (throughput 2x) | H1, H2 |
| H4 | RAG Full-Doc 0.8B | High | 1-2 días | Medio (extracción sin chunk) | H3 |
| H5 | Knowledge Sync Agent | **High** | 3-5 días | Alto (conocimiento fresco) | — |
| H6 | Calendar Reading Fix | **High** | 1-2 días | Alto (bugfix) | — |
| H7 | Web Search Output | High | 1 día | Alto (formateo) | — |
| H8 | Expand Fast Paths | High | 2-3 días | Alto (más queries sin LLM) | — |
| M1 | Conversation Distillation 0.8B | Medium | 1 día | Medio (menos latencia) | H3 |
| M2 | Tool Call Fast Path 0.8B | Medium | 1 día | Medio | H1, H3 |
| M3 | LoRA Tool Calling 0.8B | Medium | 1 día | Bajo | H1 |
| M4 | Document Summarization | Medium | 2 días | Medio (nueva feature) | M7 |
| M5 | Windows Port (Cross-Platform) | Medium | 12-15 días | Alto (nuevo OS) | pywin32, send2trash |
| M6 | Frontend Buttons Wiring | Medium | 1-2 días | Medio (UX) | — |
| M7 | Upload & Summarize API | Medium | 1 día | Medio (backend) | — |
| L1 | Dataset Synthesizer | Low | 1 día | Alto (habilita H1) | — |
| L2 | Auto Warmup | Low | 0.5 día | Bajo | H3 |
| L3 | Classifier Evaluation Pipeline | Low | 0.5 día | Bajo | H2 |
| L4 | (reserved) | — | — | — | — |
| L5 | (reserved) | — | — | — | — |

**Orden recomendado:** H5 → H6 → H7 → H8 → L1 → H1 → H2 → M5 (WinPort) → M6 → H3 → H4 → M4+M7 → M1/M2 → L2 → L3 → M3
