# Local Model Fleet Orchestrator
**Módulo propuesto para Cerebro — Agentic Personal OS**

---

## Resumen

Un subsistema que analiza dinámicamente el hardware disponible (RAM, VRAM, CPU) y la complejidad de las tareas entrantes, seleccionando automáticamente el modelo local y el nivel de cuantización óptimos — sin que el usuario intervenga. Puede reconfigurarse entre requests para nunca quedarse sin memoria.

---

## Evaluación de complejidad

| Componente | Dificultad | Motivo |
|---|---|---|
| Hardware Monitor | Baja | `psutil` + `subprocess` para GPU |
| Model Registry (YAML config) | Baja-Media | Requiere curar tabla de modelos + VRAM |
| Task Complexity Classifier | Media | Heurísticas de longitud + keywords |
| Model Selection Logic | Media | Árbol de decisión sobre RAM/VRAM disponible |
| Dynamic llama.cpp process swap | Alta | Matar/relanzar proceso tiene latencia de segundos |
| Hot-swap mid-conversation | Muy Alta | Rompe contexto; requiere serialización de KV-cache |

**Recomendación:** implementar en dos fases:
- **Fase 1 (rápida):** selección al arranque + entre conversaciones
- **Fase 2 (ambiciosa):** swap entre requests con gestión de latencia

---

## Integración con Cerebro existente

El módulo se integra limpiamente en la arquitectura actual:

```
core/
  inference/
    provider_registry.py    ← ya existe; extender con fleet_orchestrator
    fleet/                  ← nuevo submódulo
      hardware_monitor.py
      model_registry.py
      task_classifier.py
      orchestrator.py
      script_writer.py
```

- **ProviderRegistry** ya tiene fallback por RAM — el orquestador reemplaza esa lógica simple
- **Pipeline stage "intent"** (`core/pipeline/`) ya clasifica el tipo de tarea — se puede enchufar ahí la clasificación de complejidad
- **MetricsCollector** (`core/observability/`) ya registra `provider_fallbacks` — añadir `model_swaps` y `quantization_level`
- **AppState** ya expone configuración inyectable — el orquestador vive ahí

---

## Diseño detallado

### 1. Hardware Monitor (`hardware_monitor.py`)

```python
@dataclass
class HardwareSnapshot:
    ram_total_gb: float
    ram_available_gb: float
    cpu_count: int
    cpu_percent: float
    gpu_backend: str          # "metal", "cuda", "none"
    gpu_vram_total_gb: float
    gpu_vram_available_gb: float
    unified_memory: bool      # True en Apple Silicon

def snapshot() -> HardwareSnapshot:
    """Captura estado actual del hardware."""
```

**Detección de GPU:**
- Apple Silicon: `sysctl hw.memsize` + MLX para VRAM (memoria unificada = RAM compartida)
- NVIDIA: `nvidia-smi --query-gpu=memory.free,memory.total --format=csv`
- Sin GPU: modo CPU-only con llama.cpp

### 2. Model Registry (`model_registry.py`)

Archivo de configuración `~/.cerebro/models.toml`:

```toml
[[models]]
id = "qwen2.5-7b-q4"
path = "~/.cerebro/models/qwen2.5-7b-instruct-q4_k_m.gguf"
family = "qwen2.5"
params_b = 7
quant = "Q4_K_M"
ram_required_gb = 5.5
vram_required_gb = 4.8
gpu_layers = 33          # -1 = todos; 0 = CPU-only
context_length = 8192
capabilities = ["chat", "code", "reasoning"]
speed_tokens_per_sec = 45

[[models]]
id = "qwen2.5-7b-q8"
path = "~/.cerebro/models/qwen2.5-7b-instruct-q8_0.gguf"
family = "qwen2.5"
params_b = 7
quant = "Q8_0"
ram_required_gb = 9.0
vram_required_gb = 8.5
gpu_layers = 33
context_length = 8192
capabilities = ["chat", "code", "reasoning"]
speed_tokens_per_sec = 35

[[models]]
id = "qwen2.5-32b-q4"
path = "~/.cerebro/models/qwen2.5-32b-q4_k_m.gguf"
family = "qwen2.5"
params_b = 32
quant = "Q4_K_M"
ram_required_gb = 22.0
vram_required_gb = 20.0
gpu_layers = 64
context_length = 32768
capabilities = ["chat", "code", "reasoning", "analysis"]
speed_tokens_per_sec = 12

[[models]]
id = "smollm2-360m-q8"
path = "~/.cerebro/models/smollm2-360m-q8_0.gguf"
family = "smollm2"
params_b = 0.36
quant = "Q8_0"
ram_required_gb = 0.8
vram_required_gb = 0.7
gpu_layers = -1
context_length = 2048
capabilities = ["chat", "classification"]
speed_tokens_per_sec = 300
```

### 3. Task Complexity Classifier (`task_classifier.py`)

```python
class TaskComplexity(str, Enum):
    TRIVIAL = "trivial"      # respuesta factual corta
    LIGHT = "light"          # chat, resumen breve
    MEDIUM = "medium"        # RAG, código simple
    HEAVY = "heavy"          # razonamiento multi-paso, análisis largo
    MAXIMUM = "maximum"      # escritura extensa, código complejo, investigación

@dataclass
class TaskProfile:
    complexity: TaskComplexity
    requires_code: bool
    context_length_estimate: int
    required_capabilities: list[str]
```

**Heurísticas de clasificación (sin modelo adicional):**
- Longitud del prompt (tokens estimados)
- Keywords: "analiza", "investiga", "escribe un ensayo" → HEAVY/MAXIMUM
- Keywords: "qué es", "define", "cuándo" → TRIVIAL/LIGHT
- Presencia de código en el prompt → requiere `code` capability
- Número de documentos en contexto RAG
- Historial de conversación (longitud acumulada)

**Opcional (Fase 2):** usar el modelo más pequeño disponible como clasificador dedicado antes de despachar al modelo principal.

### 4. Fleet Orchestrator (`orchestrator.py`)

```python
@dataclass
class ModelSelection:
    model: ModelConfig
    gpu_layers: int
    context_length: int
    rationale: str           # logging/observabilidad

class FleetOrchestrator:
    def select_model(
        self,
        task: TaskProfile,
        hw: HardwareSnapshot,
        registry: list[ModelConfig],
    ) -> ModelSelection:
        """
        Algoritmo de selección:
        1. Filtrar modelos con RAM/VRAM disponible (con margen del 15%)
        2. Filtrar por capabilities requeridas
        3. Entre los elegibles, seleccionar el de mayor params_b
           que encaje en el hardware
        4. Si hay memoria de sobra y la tarea es HEAVY/MAXIMUM,
           subir a la siguiente cuantización disponible del mismo modelo
        5. Si la memoria es crítica (<20% libre), bajar cuantización
           o cambiar a modelo más pequeño
        """
```

**Árbol de decisión simplificado:**

```
RAM disponible > 20GB + tarea HEAVY/MAXIMUM
  → modelo 32B Q4 con GPU offload máximo

RAM disponible > 8GB + tarea MEDIUM/HEAVY
  → modelo 7B Q8 con GPU offload completo

RAM disponible > 5GB + tarea LIGHT/MEDIUM
  → modelo 7B Q4 con GPU offload parcial

RAM disponible < 5GB o tarea TRIVIAL
  → modelo pequeño (SmolLM, Phi-mini) Q8 CPU-only
```

### 5. Script Writer (`script_writer.py`)

Genera el comando de lanzamiento de llama.cpp dinámicamente:

```python
def build_llamacpp_command(selection: ModelSelection, port: int = 8080) -> list[str]:
    return [
        "./llama-server",
        "--model", str(selection.model.path),
        "--port", str(port),
        "--ctx-size", str(selection.context_length),
        "--n-gpu-layers", str(selection.gpu_layers),
        "--threads", str(os.cpu_count() or 4),
        "--batch-size", "512",
        "--flash-attn",          # si disponible
    ]
```

**Para MLX (Apple Silicon alternativo):**
```python
def build_mlx_command(model_id: str, port: int = 8080) -> list[str]:
    return [
        "python", "-m", "mlx_lm.server",
        "--model", model_id,
        "--port", str(port),
    ]
```

---

## Flujo completo (Fase 1 — selección al arranque)

```
make run
  → FleetOrchestrator.select_on_startup()
    → HardwareMonitor.snapshot()
    → ModelRegistry.load()
    → TaskProfile(complexity=MEDIUM)  # default para arranque
    → ModelSelection(model=qwen2.5-7b-q4, gpu_layers=33)
    → ScriptWriter.build_llamacpp_command(selection)
    → subprocess.Popen(command)  # lanza llama.cpp server
    → ProviderRegistry.register("llamacpp", base_url="http://localhost:8080")
  → FastAPI server arranca normalmente
```

## Flujo completo (Fase 2 — swap entre requests)

```
POST /query { "message": "Analiza en profundidad..." }
  → Pipeline stage "intent"
    → TaskClassifier.classify(message) → TaskProfile(HEAVY, requires_code=False)
  → FleetOrchestrator.maybe_swap(task_profile, current_model)
    → HardwareMonitor.snapshot()
    → ModelSelection nuevo vs actual
    → Si diferente: ProcessManager.swap(new_command)
      → llama.cpp process kill → relanzar → health check → continuar
      → latencia extra: ~3-8 segundos (notificar al cliente vía SSE)
  → InferenceEngine.query(...)
```

---

## Observabilidad (extensión de MetricsCollector)

```python
# Añadir a ResponseMetadata
model_id: str
quantization: str
gpu_layers_used: int
model_swap_occurred: bool
hardware_snapshot: dict   # ram_available, gpu_available al momento del request
```

Nuevas métricas en `/status`:
- `current_model`: modelo activo
- `model_swaps_session`: número de swaps en la sesión
- `ram_pressure`: porcentaje de RAM usada
- `selection_rationale`: por qué se eligió ese modelo

---

## Qué NO hacer (para mantener scope)

- No descargar modelos automáticamente (solo gestionar los que ya existen en disco)
- No soportar múltiples modelos en paralelo (un solo servidor llama.cpp activo)
- No re-entrenar ni hacer fine-tuning
- No gestionar modelos remotos (API de OpenAI, Anthropic) — Cerebro es local-first

---

## Dependencias nuevas

```toml
# pyproject.toml
psutil = ">=5.9"          # RAM/CPU monitoring
tomllib = ">=1.0"         # ya existe en Python 3.11 stdlib
# GPU: sin deps extra — nvidia-smi vía subprocess, MLX ya instalado
```

---

## Plan de implementación

### Fase 1 — Selección inteligente al arranque (1-2 días)
1. `hardware_monitor.py` + tests
2. `model_registry.py` + `~/.cerebro/models.toml` con tus modelos actuales
3. `orchestrator.py` (solo lógica de selección, sin swap)
4. `script_writer.py` (genera el comando llama.cpp)
5. Integrar en `main.py` antes de `ProviderRegistry.setup()`
6. Extender `/status` con `current_model` y `hardware_snapshot`

### Fase 2 — Swap dinámico entre requests (3-5 días)
1. `ProcessManager` — gestión del proceso llama.cpp (PID tracking, health checks)
2. Integrar `TaskClassifier` en el pipeline stage "intent"
3. SSE notification al frontend cuando hay un swap en curso
4. Test de integración: simular RAM alta/baja y verificar selección correcta
5. UI: indicador del modelo activo en la tray

---

## Veredicto final

**¿Es complicado de implementar en Cerebro?**

La Fase 1 encaja casi perfectamente con la arquitectura existente — el `ProviderRegistry` ya tiene el concepto de selección dinámica, solo necesita alimentarse del hardware real en vez de config estática. Estimado: 1-2 días.

La Fase 2 (swap dinámico mid-session) es el módulo más ambicioso que habrías construido en el proyecto, porque introduce gestión de procesos con estado y latencia observable. La dificultad real no es el código sino la experiencia de usuario durante los 3-8 segundos de swap. Estimado: 3-5 días.

**Recomendación:** implementar Fase 1 primero — ya te da el 80% del valor (nunca quedarte sin RAM, siempre el modelo más capaz disponible) con el 20% del riesgo.
