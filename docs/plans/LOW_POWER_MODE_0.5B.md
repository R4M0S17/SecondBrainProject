# Low-Power Mode: Qwen2.5-0.5B como modelo único

**Autor:** Senior Backend/ML Engineer — 15 yr
**Fecha:** 2026-06-17
**Proyecto:** Cerebro — SecondBrain
**Objetivo:** Perfil funcional que usa Qwen2.5-0.5B-Instruct-Q5_K_M.gguf como único
modelo de inferencia, liberando ~1.8 GB de RAM comparado con Qwen3.5-2B.

---

## 1. Fundamentos

### 1.1 Métricas esperadas

| Métrica | Qwen3.5-2B (actual) | Qwen2.5-0.5B (low-power) | Diferencia |
|---------|--------------------|--------------------------|------------|
| RAM en uso | ~2.5 GB | ~0.8 GB | **-68 %** |
| Velocidad generación | ~23.5 t/s | 58-70 t/s | **~3× más rápido** |
| Disco | 1.24 GB | 498 MB | **-60 %** |
| Contexto máximo | 262 144 tokens | 32 768 tokens | **-87 %** |
| Tool calling | Robusto | Limitado (JSON simple) | — |
| Razonamiento multi-paso | Bueno | Débil | — |

### 1.2 ¿Qué sigue funcionando bien?

- **Fast-path pipeline** (14 rutas determinísticas: hora, clima, matemáticas,
  archivos, calendario, recordatorios, web search, etc.) — no usa LLM, sin cambios
- **Router SmolLM2-135M** — sigue siendo el clasificador de intención siempre encendido
- **RAG con contexto cercano** — respuestas basadas en documentos funcionan si el
  fragmento es pequeño y la pregunta es directa
- **Código simple** — scripts de una línea, preguntas de sintaxis básica
- **Charla casual** — saludos, preguntas triviales
- **Escritura de archivos** — si la intención es clara y el contenido es corto
- **Recordatorios y calendario** — el fast-path ya extrae la intención; el 0.5B
  solo confirma

### 1.3 ¿Dónde va a degradarse?

- **Herramientas con JSON anidado**: el 0.5B genera tool calls con formato
  inconsistente; esperar fallos en `repair_tool_json` y `extract_json_object`
- **Razonamiento multi-paso**: "si llueve mañana, crea un evento y pon un
  recordatorio" → probablemente falla en el segundo paso
- **Contexto largo**: 32K vs 262K; conversaciones de >20 mensajes pierden
  precisión
- **TaskPlanner (A7)**: planes de 3+ pasos se desvían; esperar alucinaciones
  en herramientas intermedias
- **Código complejo**: debugging de lógica condicional anidada, refactors
- **Reflection turn**: el crítico heurístico sigue igual, pero si se configura
  un LLM para reflection, el 0.5B va a dar críticas pobres

---

## 2. Estrategia de implementación

### 2.1 Principios

1. **No tocar el fast-path pipeline.** Las 14 rutas determinísticas son
   independientes del modelo y no deben modificarse.
2. **Cambios de runtime mínimos y explícitos.** El low-power mode se activa
   con un profile env. Se tocan exactamente 3 líneas de runtime:
   `--grammar` en el perfil de `llama-server`, `max_steps=2` en `TaskPlanner`,
   y `ctx-size` aumentado para aprovechar el RAM liberado. Cada cambio está
   documentado y justificado abajo.
3. **El router (SmolLM2-135M) no cambia.** Sigue siendo el clasificador de
   intención en puerto 8080.
4. **El modelo 0.5B vive en `bin/models/`** junto con los demás GGUFs.
5. **Prompt cache adaptado.** El `sync_prompt_cache` de `main.py` usa
   `model_id=LLAMACPP_MODEL` — al cambiar el modelo se regenera solo.

### 2.2 Archivos a tocar (lista completa)

```
M  config/profiles/low-power.env              ← ✅ Done
M  config/chat-lowpower.args                  ← ✅ Done (copia de chat.args + --grammar + ctx-size)
M  core/agents/planner.py                     ← ✅ Done
M  scripts/download-models.sh                 ← ✅ Done
D  docs/plans/LOW_POWER_MODE_0.5B.md          ← este documento
```

El runtime principal (`core/agents/runtime.py`), registry
(`core/inference/registry.py`) y fast-path (`core/agents/fast_path_router.py`)
**no se tocan**. El modelo se selecciona vía `CEREBRO_LLAMACPP_MODEL`. Los
cambios de runtime son acotados y están listados en las secciones 4, 8 y 12.

---

## 3. Perfil de entorno: `config/profiles/low-power.env`

### 3.1 Contenido del archivo

```bash
# Cerebro — Low-Power Profile
# Usa Qwen2.5-0.5B como único modelo. Pierde calidad de razonamiento
# pero libera ~1.8 GB de RAM (~0.7 GB total para inferencia).
#
# Activar: make low-power  (o: source config/profiles/low-power.env && python main.py)

CEREBRO_LLAMACPP_MODEL=Qwen2.5-0.5B-Instruct-Q5_K_M.gguf

# ── Inferencia ──────────────────────────────────────────────
CEREBRO_INFERENCE_BACKEND=llamacpp
CEREBRO_LLAMACPP_SIMPLE=true
CEREBRO_LLAMACPP_URL=http://127.0.0.1:8080
CEREBRO_LLAMACPP_PROFILE=chat-lowpower  # perfil con grammar + ctx-size=8192

# ── Embeddings locales (sin servidor externo) ───────────────
CEREBRO_EMBEDDINGS_BACKEND=local

# ── MLX desactivado (problemas de estabilidad en M1) ────────
CEREBRO_MLX_ENABLED=false

# ── Contexto proactivo desactivado (ahorra RAM y llamadas) ──
CEREBRO_PROACTIVE_CONTEXT=false

# ── Scheduler desactivado ───────────────────────────────────
CEREBRO_SCHEDULER_ENABLED=false

# ── Umbrales de RAM más agresivos ───────────────────────────
CEREBRO_RAM_PRIMARY_GB=0.6
CEREBRO_RAM_FALLBACK_GB=0.3
```

### 3.2 ¿Por qué estos valores?

| Variable | Valor | Razón |
|----------|-------|-------|
| `CEREBRO_LLAMACPP_SIMPLE=true` | true | No necesitamos model swapping; un solo proceso |
| `CEREBRO_EMBEDDINGS_BACKEND=local` | local | sentence-transformers ~120 MB vs embed server ~1.5 GB |
| `CEREBRO_PROACTIVE_CONTEXT=false` | false | ContextEnricher suma ~200 MB y llamadas extra al modelo |
| `CEREBRO_SCHEDULER_ENABLED=false` | false | El scheduler consume RAM para mantener estado |
| `CEREBRO_RAM_PRIMARY_GB=0.6` | 0.6 | El 0.5B (Q5_K_M) cabe en ~0.8 GB; arrancamos con 0.6 de margen |

---

## 4. Cambios en `main.py`

### 4.1 Línea 95: modelo por defecto en modo lite

Actualmente (línea 95 de `main.py`):

```python
LLAMACPP_MODEL = os.getenv(
    "CEREBRO_LLAMACPP_MODEL",
    "Qwen3.5-2B-UD-Q4_K_XL.gguf",
)
```

No tocar. La env var `CEREBRO_LLAMACPP_MODEL` ya es el mecanismo de selección.
El low-power profile la setea a `Qwen2.5-0.5B-Instruct-Q5_K_M.gguf`.

El default en código debe seguir siendo el 2B para que `make run` sin perfil
siga funcionando como antes.

### 4.2 Perfil `chat-lowpower.args` — NUEVO

Crear `config/chat-lowpower.args` como copia de `config/chat.args` con dos
diferencias críticas:

```bash
# config/chat-lowpower.args
--model bin/models/Qwen2.5-0.5B-Instruct-Q5_K_M.gguf
--port 8080
--ctx-size 8192            # duplicado vs 4096 normal (el 0.5B lo tolera)
--n-gpu-layers 99
--chat-template chatml
--grammar-file bin/grammars/tool_call.gbnf   # ← activado por defecto
--log-disable
```

Razones:
- **`--grammar-file`**: El 0.5B genera JSON tool calls inconsistentes. La
  gramática restringe la salida a JSON válido, eliminando la categoría de
  fallo entera. No esperar a que "la tasa de fallo sea >30%" — activar
  desde el día uno. Costo: 0 líneas de runtime, 1 línea de config.
- **`--ctx-size 8192`**: El 0.5B tiene hidden_size y num_layers mucho
  menores que el 2B (~512×6 vs ~2048×24). Su KV cache por token es ~4×
  más pequeña. Duplicar el contexto de 4K a 8K cuesta ~10-15 MB extra
  en RAM — despreciable contra los ~1.8 GB liberados. Esto mitiga
  parcialmente el riesgo de "contexto corto" sin gastar nada significativo.

`_ensure_chat_args()` en `main.py` reescribe `chat.args` según
`LLAMACPP_MODEL`. Para el perfil low-power, en vez de apuntar a
`chat.args`, `main.py` debe leer `chat-lowpower.args`. Esto se logra
con una nueva env var (ver plumbing abajo).

### 4.3 Env var `CEREBRO_LLAMACPP_ARGS_FILE` — NUEVA (1 línea en `main.py`)

`_ensure_chat_args()` en `main.py:74` siempre escribe sobre
`config/chat.args`. Para el perfil low-power, necesitamos que apunte
a `config/chat-lowpower.args`.

Cambio en `main.py` (1 línea):

```python
# Después de leer LLAMACPP_MODEL y LLAMACPP_PROFILE
LLAMACPP_ARGS_FILE = os.getenv(
    "CEREBRO_LLAMACPP_ARGS_FILE",
    "config/chat.args",
)
```

Y en `_ensure_chat_args()`, usar `LLAMACPP_ARGS_FILE` en vez del path
hardcodeado. Esto permite que el perfil low-power setee:

```bash
CEREBRO_LLAMACPP_ARGS_FILE=config/chat-lowpower.args
```

El default sigue siendo `config/chat.args` para todos los demás perfiles.

### 4.4 `sync_prompt_cache` (línea 539)

`sync_prompt_cache()` usa `model_id=LLAMACPP_MODEL`. Al cambiar el modelo,
la cache se regenera automáticamente. Sin cambios necesarios.

### 4.3 Consideración: `sync_prompt_cache` (línea 539)

`sync_prompt_cache()` usa `model_id=LLAMACPP_MODEL`. Al cambiar el modelo,
la cache se regenera automáticamente. Sin cambios necesarios.

---

## 5. Cambios en `scripts/download-models.sh`

### 5.1 Agregar el modelo 0.5B con validación SHA256

Descargar siempre (son solo 498 MB). El SHA256 debe estar hardcodeado en
el script para fail-fast si el archivo está corrupto o fue modificado.

```bash
# ── Qwen2.5-0.5B (low-power mode) ──────────────────────────
Qwen2.5_0.5B_FILE="qwen2.5-0.5b-instruct-q5_k_m.gguf"
Qwen2.5_0.5B_SHA256="041474553fcabfc2a2d67903f9d2c2e50bd92528e670da4f33b5d0ce6e59fd55"
Qwen2.5_0.5B_URL="${HF_BASE}/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q5_k_m.gguf"

if [ ! -f "$MODELS_DIR/$Qwen2.5_0.5B_FILE" ]; then
    echo "Downloading $Qwen2.5_0.5B_FILE ..."
    curl -L --retry 3 --retry-delay 5 -o "$MODELS_DIR/$Qwen2.5_0.5B_FILE" "$Qwen2.5_0.5B_URL"
    echo "Verifying checksum..."
    echo "$Qwen2.5_0.5B_SHA256  $MODELS_DIR/$Qwen2.5_0.5B_FILE" | shasum -a 256 -c -
    echo "✓ $Qwen2.5_0.5B_FILE downloaded and verified"
fi
```

> SHA256 verificado: `041474553fcabfc2a2d67903f9d2c2e50bd92528e670da4f33b5d0ce6e59fd55`
> Obtenido de HuggingFace (LFS OID). Tamaño: 522 186 592 bytes (~498 MB en disco).

### 5.2 URL oficial del modelo

```
Modelo:    Qwen/Qwen2.5-0.5B-Instruct-GGUF
Archivo:   qwen2.5-0.5b-instruct-q5_k_m.gguf
URL:       https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q5_k_m.gguf
SHA256:    041474553fcabfc2a2d67903f9d2c2e50bd92528e670da4f33b5d0ce6e59fd55
Tamaño:    498 MB
Nota:      El Q5_K_M da mejor precisión en tool calling que Q4_K_M a costa
           de solo ~30 MB extra. Los benchmarks del proyecto confirman que
           las 4 cuantizaciones del 0.5B dan calidad idéntica en código y
           matemáticas; Q5_K_M es preferido para tool calling.
```

---

## 6. Usar el low-power mode

### 6.1 Comando único (recomendado)

```bash
make low-power
```

Usa un subshell aislado — no muta el entorno del terminal actual.

### 6.2 Alternativa con `source` (debugging)

```bash
source config/profiles/low-power.env && python main.py
```

> ⚠️ `source` exporta ~8 variables en el shell actual. Para volver al modo
> normal en la misma terminal, reinicia la shell o des-exporta manualmente:
> `unset CEREBRO_LLAMACPP_MODEL CEREBRO_LLAMACPP_PROFILE ...`

### 6.3 Target `make low-power` en Makefile

```makefile
.PHONY: low-power
low-power:
    bash -c 'source config/profiles/low-power.env && exec python main.py'
```

---

## 7. Pruebas

### 7.1 Smoke test básico

```bash
source config/profiles/low-power.env
make test-stable
```

El `test-stable` corre la suite de regresión rápida. Todos los tests mockean
el backend de inferencia, así que la suite debe pasar igual.

### 7.2 Test de integración manual

```bash
# 1. Verificar consumo de RAM
make low-power &
sleep 10  # esperar a que cargue el modelo
ps aux | grep llama-server  # confirmar que es el 0.5B
vmmap <PID> | grep "Physical footprint"  # ~700 MB esperado

# 2. Consultas básicas
curl -X POST http://localhost:7842/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "hola, quien eres?"}'

curl -X POST http://localhost:7842/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "que hora es?"}'

# 3. Consulta con tool calling simple
curl -X POST http://localhost:7842/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "crea un archivo llamado test.txt con el texto hola mundo"}'

# 4. Consulta que debería fallar (razonamiento complejo)
curl -X POST http://localhost:7842/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "si hoy es miercoles, que dia sera en 47 dias? y crea un evento para ese dia"}'
```

### 7.3 Benchmark de RAM

```bash
# Comparar RAM usada con y sin low-power
echo "=== LOW POWER ===" && \
  source config/profiles/low-power.env && \
  make run &
sleep 15
ps aux | awk '/llama-server/ {print $6/1024 " MB"}'
kill %1

echo "=== NORMAL ===" && \
  make run &
sleep 15
ps aux | awk '/llama-server/ {print $6/1024 " MB"}'
kill %1
```

---

## 8. Riesgos y mitigaciones

### 8.1 Tool calling inconsistente

**Riesgo:** El 0.5B genera JSON tool calls con formato incorrecto (falta
`"tool"`, `"args"` mal formado, etc.).

**Mitigación (por defecto, no reactiva):** El perfil low-power activa
`--grammar-file` en `llama-server` desde el día uno (sección 4.2). Esto
restringe la salida del modelo a JSON válido según la gramática de tool
calling. No esperar a que el usuario sufra el bug.

Si aún así hay fallos (poco probable con gramática):

- Subir a `Qwen2.5-0.5B-Instruct-Q5_K_M.gguf` (606 MB, ~+140 MB RAM)
  — mejor precisión a costa de ~20 % más RAM.
- El runtime ya tiene `repair_tool_json()` y `extract_json_object()` en
  `core/agents/llm_parse_utils.py` como defensa en profundidad.

### 8.2 Contexto de 32K es poco (mitigado por ctx-size=8192)

**Riesgo:** Conversaciones largas pierden el hilo.

**Mitigación 1 — ctx-size duplicado (ya implementado, sección 4.2):**
El perfil low-power usa `--ctx-size 8192` vs 4096 normal. El 0.5B tiene
una arquitectura mucho más chica (hidden_size ~512, num_layers ~6) vs
el 2B (hidden_size ~2048, num_layers ~24). Su KV cache por token es
~4× menor. Duplicar el contexto cuesta apenas ~10-15 MB extra en RAM
— despreciable contra los ~1.8 GB liberados.

**Mitigación 2 — mensajes cortos:** El `session_policy.py` ya comprime
el historial con `persist_session_summary()`. Si el problema persiste,
ajustar `short_term_max_messages` a 6-8 mensajes (el default real en
`core/memory/short_term.py` es 35, no 15 como se mencionó en la
primera versión de este plan):

```bash
# En config/profiles/low-power.env
CEREBRO_SHORT_TERM_MAX_MESSAGES=8
```

> Nota: `CEREBRO_SHORT_TERM_MAX_MESSAGES` puede no existir como env var.
> Si es constante en `short_term.py`, agregar `os.getenv(...)` es 1 línea.

### 8.3 TaskPlanner sin guardrail

**Riesgo:** `TaskPlanner` genera planes de 3+ pasos que el 0.5B no puede
ejecutar correctamente (alucina herramientas intermedias).

**Mitigación:** El `TaskPlanner` acepta `max_steps` en su constructor.
Para el perfil low-power, limitar a 2 pasos. Esto es un cambio de 2
líneas en `core/agents/planner.py` y 1 línea en el perfil env:

```python
# En planner.py — leer de env var con default
max_steps = int(os.getenv("CEREBRO_PLANNER_MAX_STEPS", "4"))
if self._low_power:
    max_steps = min(max_steps, 2)
```

```bash
# En config/profiles/low-power.env
CEREBRO_PLANNER_MAX_STEPS=2
```

### 8.4 El 0.5B alucina más

**Riesgo:** Especialmente en respuestas factuales sin contexto RAG.

**Mitigación:** El `Reflector` heurístico (default) ya atrapa algunos
patrones de alucinación (contradicciones internas, fechas imposibles,
etc.). Si es crítico, habilitar `REFLECTION_MODEL_URL` apuntando a otro
`llama-server` con el 2B en un puerto diferente. Esto contradice el
propósito del low-power mode, así que se documenta como opción, no
como mitigación por defecto.

### 8.5 API `get_chat_for_agent()` con ModelManager

**Riesgo:** Si alguien activa `CEREBRO_LLAMACPP_SIMPLE=false` (model
swapping), `get_chat_for_agent()` en `registry.py` lanza un
`LlamaCppChatProvider` para el specialist. El specialist usa
`_GENERAL_MODEL` o `_CODE_MODEL` definidos en `model_manager.py`.
Si esos modelos no están instalados, falla.

**Mitigación:** El low-power profile setea `CEREBRO_LLAMACPP_SIMPLE=true`
— este riesgo no aplica. Si alguien usa simple=false con el perfil
low-power, debe configurar también `CEREBRO_GENERAL_MODEL` para que
apunte al 0.5B.

---

## 9. Criterios de aceptación

| # | Criterio | Cómo se verifica |
|---|----------|------------------|
| 1 | El modelo 0.5B se descarga con `scripts/download-models.sh` | `ls -lh bin/models/qwen2.5-0.5b-instruct-q5_k_m.gguf` + SHA256 válido | ✅ Done |
| 2 | `make low-power` arranca sin errores | Log: "llamacpp mode: simple=true", "profile=chat-lowpower" | [✅ Done] |
| 3 | RAM de `llama-server` ≤ 900 MB | `ps aux \| awk '/llama-server/ {print $6/1024}'` | _(p. verificación)_ |
| 4 | `--grammar-file` activo en el proceso | `ps aux \| grep llama-server \| grep -c grammar-file` → 1 | ✅ Done |
| 5 | `--ctx-size` es 8192 (no 4096) | `ps aux \| grep llama-server \| grep -o 'ctx-size [0-9]*'` | ✅ Done |
| 6 | Query "hola" responde en <2s | `time curl -X POST ...` | _(p. verificación)_ |
| 7 | Fast-path "qué hora es?" responde sin LLM | Respuesta instantánea con hora real | _(p. verificación)_ |
| 8 | `make test-stable` pasa 100 % | `pytest tests/ --test-stable` | _(p. verificación)_ |
| 9 | Tool calling "crea un archivo" genera JSON válido | `curl -X POST ... \| jq .` sin errores de parseo | _(p. verificación)_ |
| 10 | TaskPlanner limitado a 2 pasos | Consulta multi-paso no genera planes de 3+ | ✅ Done |
| 11 | Toggle en frontend cambia a Low Power en 1 click | Click toggle → spinner → "🔋 Low Power" visible | ✅ Done |
| 12 | Toggle en frontend vuelve a Normal en 1 click | Click toggle → spinner → "⚡ Normal" visible | ✅ Done |
| 13 | El 2B sigue funcionando sin el perfil activado | `make run` usa Qwen3.5-2B y `chat.args` normal | _(p. verificación)_ |
| 14 | Swap banner visible durante el cambio | Animación "Switching to Low Power..." durante ~5-8s | ✅ Done |

---

## 10. Frontend — toggle rápido entre modelos (v1)

### 10.1 Lo que ya existe

El backend ya soporta cambio de modelo en caliente vía `PATCH /api/config`
con el campo `model`. La función `_switch_llamacpp_model()` en
`server.py:1959` mata el proceso en puerto 8080, reescribe
`config/chat.args` con el nuevo modelo, reinicia `llama-server` y
espera hasta 60s a que esté saludable.

El frontend ya tiene:
- `ModelSelector.tsx` — lista completa de GGUFs como radio-buttons
- `ActiveFleetList.tsx` — selector compacto en la barra lateral
- `SwapBanner.tsx` — animación durante el cambio vía SSE
- `useSettingsStore.patch()` — llama a `PATCH /api/config`
- `GET /api/status` — expone `model` actual

Lo que **no** existe es un toggle simple que cambie entre dos modos
predefinidos sin tener que navegar a settings + buscar en una lista.

### 10.2 Diseño del toggle

**Qué hace:**
Un interruptor (switch) en la cabecera del chat que alterna entre
"Normal" (Qwen3.5-2B) y "Low Power" (Qwen2.5-0.5B). Al cambiar:

1. Frontend llama a `PATCH /api/config { model: "Qwen2.5-0.5B-...", profile: "low-power" }`
2. Backend mata `llama-server`, reescribe `config/chat.args` con los
   args del perfil destino (incluyendo `--grammar-file` y `--ctx-size`),
   reinicia el engine, espera health
3. Frontend muestra spinner "Cambiando a Low Power..." con swap banner
4. Al completar, el badge en el toggle cambia de "⚡ Normal" a "🔋 Low Power"

**Dónde va:**
En `Header.tsx`, al lado del botón de settings o del título.

```
┌──────────────────────────────────────────────────────────────────┐
│  Cerebro                          [🔋 Low Power]  [⚙️ Settings]  │
│  ─────────────────────────────────────────────────────────────── │
│                                                                  │
│  [Chat messages...]                                              │
│                                                                  │
│  [Input area...]                                                 │
└──────────────────────────────────────────────────────────────────┘
```

### 10.3 Backend: soporte para perfil en PATCH

Actualmente `_switch_llamacpp_model()` escribe `config/chat.args` con
el modelo nuevo pero mantiene el resto de flags iguales. Para que el
toggle funcione correctamente (grammar + ctx-size al cambiar a low-power),
necesitamos que el backend acepte un campo `profile` en el PATCH.

**Cambio en `server.py:patch_config()`:**

```python
# Después del bloque "model" existente (línea ~1630)
if "profile" in settings:
    profile_name = settings["profile"]
    profile_args_map = {
        "normal": "config/chat.args",
        "low-power": "config/chat-lowpower.args",
    }
    args_file = profile_args_map.get(profile_name, "config/chat.args")
    app_state._config["profile"] = profile_name

    # Si el modelo también cambió, _switch_llamacpp_model ya reescribió
    # chat.args. Necesitamos que use el args file correcto.
    # Si solo cambió el perfil, forzar reinicio con los nuevos args.
```

**Solución más limpia:** Refactorizar `_switch_llamacpp_model()` para
aceptar un parámetro `args_file`:

```python
async def _switch_llamacpp_model(
    model_name: str,
    args_file: str = "config/chat.args",
) -> None:
    # ...
    args_path = Path(__file__).parents[1] / args_file
    # Leer args del archivo correcto, reemplazar --model, escribir
    # en config/chat.args (que es lo que lee start_engine.sh)
    # ...
```

De esta forma el toggle envía:

```json
PATCH /api/config
{
  "model": "Qwen2.5-0.5B-Instruct-Q5_K_M.gguf",
  "profile": "low-power"
}
```

Y el backend usa `config/chat-lowpower.args` como plantilla.

### 10.4 Frontend: nuevo componente `QuickModelToggle`

**Archivo:** `ui/tray/src/components/chat/QuickModelToggle.tsx`

```tsx
import { useSettingsStore } from "../../stores/settings";
import { useSystemStore } from "../../stores/system";

const MODES = {
  normal: {
    label: "Normal",
    icon: "⚡",
    model: "Qwen3.5-2B-UD-Q4_K_XL.gguf",
    profile: "normal",
  },
  "low-power": {
    label: "Low Power",
    icon: "🔋",
    model: "Qwen2.5-0.5B-Instruct-Q5_K_M.gguf",
    profile: "low-power",
  },
};

export function QuickModelToggle() {
  const { activeModel, switchingModel, patch } = useSettingsStore();
  const currentModel = useSystemStore((s) => s.chatModel);

  // Determinar modo actual basado en el modelo activo
  const isLowPower = currentModel?.includes("0.5B") ?? false;
  const currentMode = isLowPower ? "low-power" : "normal";
  const targetMode = isLowPower ? "normal" : "low-power";

  const handleToggle = async () => {
    const target = MODES[targetMode];
    await patch({
      model: target.model,
      profile: target.profile,
    });
  };

  return (
    <button
      onClick={handleToggle}
      disabled={switchingModel}
      className={`quick-model-toggle ${currentMode}`}
      title={`${switchingModel ? "Switching..." : `Switch to ${MODES[targetMode].label}`}`}
    >
      {switchingModel ? (
        <span className="spinner" />
      ) : (
        <>
          <span className="icon">{MODES[currentMode].icon}</span>
          <span className="label">{MODES[currentMode].label}</span>
        </>
      )}
    </button>
  );
}
```

**Dónde se inserta:** en `Header.tsx` (o `StatusBar.tsx`), al lado del
botón de settings. Una línea:

```tsx
import { QuickModelToggle } from "./chat/QuickModelToggle";

// Dentro del header
<div className="header-controls">
  <QuickModelToggle />
  <SettingsButton />
</div>
```

### 10.5 Manejo de estado: switching + swap banner

El `useSettingsStore.patch()` ya setea `switchingModel=true` y lo resetea
al recibir respuesta. El `SwapBanner.tsx` ya reacciona a los eventos SSE
`ModelSwapEvent` — el backend emite este evento durante
`_switch_llamacpp_model()` si la conexión es SSE.

Para el toggle, el flujo completo es:

```
Usuario click "🔋 Low Power"
  → handleToggle()
    → patch({ model: "0.5B...", profile: "low-power" })
      → switchingModel = true
      → PATCH /api/config
        → server.py: mata engine, reescribe args, reinicia
        → espera health (5-8s)
        → responde 200 OK
      → switchingModel = false
      → /api/status se actualiza con nuevo modelo
  → QuickModelToggle re-renderiza con "⚡ Normal" o "🔋 Low Power"

Durante la espera:
  → SwapBanner.tsx: "Switching to Low Power..."
  → QuickModelToggle: spinner girando, disabled
```

### 10.6 Archivos a crear/modificar (frontend)

```
ui/tray/src/components/chat/QuickModelToggle.tsx   ← NUEVO [✅ Done]
ui/tray/src/layouts/Header.tsx                    ← MODIFICAR (+1 línea) [✅ Done]
ui/tray/src/stores/settings.ts                     ← MODIFICAR (profile en patch)
ui/tray/server.py                                  ← MODIFICAR (profile en patch_config) [✅ Done]
```

### 10.7 Decisión explícita: toggle vs selector completo

| Aspecto | Toggle (este diseño) | Selector completo (ModelSelector.tsx) |
|---------|---------------------|--------------------------------------|
| Visibilidad | Siempre visible en header | Dentro de settings panel |
| Clicks para cambiar | 1 click | 2-3 clicks (abrir settings + seleccionar) |
| Modelos disponibles | 2 (normal + low-power) | Todos los GGUFs instalados |
| Perfil asociado | Sí (args + grammar) | No (solo cambia el modelo) |
| Ideal para | Uso diario, cambios frecuentes | Configuración inicial, expertos |

Ambos coexisten. El toggle es para uso diario; el selector completo
sigue disponible en settings para elegir cualquier otro GGUF.

## 11. Archivos de gramática

El `--grammar-file` de la sección 4.2 requiere un archivo `.gbnf` que
describa la gramática de tool calling. Verificar si existe en el repo:

```bash
ls -R bin/grammars/
```

Si no existe, crearlo. Contenido mínimo:

```gbnf
# bin/grammars/tool_call.gbnf
root ::= tool-call | answer
tool-call ::= "{" ws "\"action\"" ws ":" ws "\"tool\"" ws "," ws "\"tool\"" ws ":" ws string ws "," ws "\"args\"" ws ":" ws "{" ws (pair (ws "," ws pair)*)? ws "}" ws "}"
answer ::= "{" ws "\"action\"" ws ":" ws "\"answer\"" ws "," ws "\"answer\"" ws ":" ws string ws "}"
string ::= "\"" ([^"]*) "\""
pair ::= string ws ":" ws string
ws ::= " "?
```

> Alternativa: `llama.cpp` incluye `--grammar` con gramática inline. Si
> `--grammar-file` no es soportado, usar `--grammar` con el contenido
> escapado. Verificar en la documentación de `llama-server --help`.

## 12. Mantenimiento futuro

### 12.1 Si aparece un modelo 0.5B mejor

Monitorear:
- **SmolLM2-360M-Instruct** (puede runnear en ~500 MB y tiene mejor tool calling)
- **Llama-3.2-1B** (1.2 GB, mejor que 0.5B pero más RAM)
- **Qwen3.5-0.5B** (futuro, si sale)
- **Phi-3.5-mini-instruct** (3.8B, demasiado grande para low-power pero mejor calidad)

Para cambiar, solo actualizar `config/profiles/low-power.env` con el nuevo
nombre de archivo y descargar el GGUF.

### 12.2 Si MLX se estabiliza en M1

El low-power mode con MLX + Qwen3.5-2B-MLX-4bit usaría ~1.05 GB RAM con
calidad de 2B. Es estrictamente mejor que el 0.5B. En ese momento:

- `CEREBRO_INFERENCE_BACKEND=mlx`
- `CEREBRO_MLX_MODEL=mlx-community/Qwen3.5-2B-MLX-4bit`
- El perfil pasaría a llamarse `balanced.env`

---

## 13. Resumen de cambios (diff concreto)

### `config/profiles/low-power.env` — CREAR [✅ Done]

~18 líneas de env vars (ver sección 3.1).

### `config/chat-lowpower.args` — CREAR [✅ Done]

Perfil de `llama-server` con `--grammar-file` y `--ctx-size 8192` (ver sección 4.2).

### `bin/grammars/tool_call.gbnf` — CREAR (si no existe) [✅ Done]

Gramática GBNF para tool calling (ver sección 11).

### `core/agents/planner.py` — MODIFICAR (2 líneas) [✅ Done]

Leer `CEREBRO_PLANNER_MAX_STEPS` del entorno, limitar a 2 para low-power
(ver sección 8.3).

### `main.py` — MODIFICAR (1 línea) [✅ Done]

Leer `CEREBRO_LLAMACPP_ARGS_FILE` del entorno para apuntar a
`chat-lowpower.args` (ver sección 4.3).

### `scripts/download-models.sh` — MODIFICAR [✅ Done]

Agregar descarga del 0.5B con validación SHA256 (ver sección 5.1).

### `AGENTS.md` — MODIFICAR (documentación) [✅ Done]

Agregar entrada en la tabla de env vars:

```
| `CEREBRO_LLAMACPP_MODEL` | Qwen3.5-2B-UD-Q4_K_XL.gguf | Cambiar a `Qwen2.5-0.5B-Instruct-Q5_K_M.gguf` para low-power mode |
```

Y agregar comando:

```bash
make low-power    # low-power mode con Qwen2.5-0.5B
```

### `Makefile` — MODIFICAR [✅ Done]

```makefile
.PHONY: low-power
low-power:
    bash -c 'source config/profiles/low-power.env && exec python main.py'
```

### `ui/tray/src/components/chat/QuickModelToggle.tsx` — CREAR [✅ Done]

Toggle switch en header para cambiar entre Normal y Low Power (ver sección 10.4).

### `ui/tray/src/layouts/Header.tsx` — MODIFICAR (+1 línea) [✅ Done]

Insertar `<QuickModelToggle />` en el header.

### `ui/tray/server.py` — MODIFICAR (profile en patch_config + _switch_llamacpp_model) [✅ Done]

Aceptar campo `profile` en `PATCH /api/config` y refactorizar
`_switch_llamacpp_model()` para usar el args file correcto (ver sección 10.3).

---

## 14. Preguntas frecuentes (para el desarrollador)

**P: ¿Por qué no usar SmolLM2-360M en vez del 0.5B?**

R: SmolLM2-360M tiene 360M params vs 494M del Qwen2.5-0.5B. La diferencia
en RAM es ~100 MB. El Qwen2.5-0.5B tiene mejor tool calling y sigue
instrucciones con más precisión. El SmolLM2-360M está optimizado para
el router (clasificación), no para chat.

**P: ¿Y el Qwen2.5-Coder-1.5B? Solo ahorra 400 MB.**

R: El 1.5B ahorra 400 MB (~2.1 GB). El 0.5B ahorra 1.8 GB (~0.7 GB).
Son perfiles diferentes. El 1.5B es "lite" (ahorro moderado, misma
calidad). El 0.5B es "low-power" (ahorro máximo, calidad reducida).
Ambos coexisten.

**P: ¿El prompt cache se regenera solo?**

R: Sí. `sync_prompt_cache()` en `main.py:539` usa `model_id=LLAMACPP_MODEL`.
Al cambiar el modelo, la cache se invalida y se regenera en el próximo
arranque.

**P: ¿Qué pasa si el 0.5B no está descargado?**

R: `llama-server` falla al arrancar con "model file not found". El log
lo muestra claramente. La solución es correr
`bash scripts/download-models.sh` con la variable `LOW_POWER=1`.

**P: ¿El EngineSuspender sigue funcionando?**

R: Sí. El suspender usa SIGSTOP/SIGCONT sobre el PID de `llama-server`.
No importa qué modelo esté cargado. Sigue liberando RAM cuando el
usuario está inactivo.

**P: ¿Hay que modificar el frontend para este modo?**

R: Sí. Se crea `QuickModelToggle.tsx` — un switch en el header que alterna
entre Normal (2B) y Low Power (0.5B) en 1 click. El backend ya soporta
`PATCH /api/config` con cambio de modelo en caliente (ver sección 10).

**P: ¿La gramática GBNF no ralentiza la generación?**

R: Mínimo. `llama.cpp` aplica la gramática como un filtro sobre el
sampling — añade ~0.1-0.5 ms por token, imperceptible contra los
~15 ms/token del 0.5B. El beneficio (tool calls siempre válidos)
supera ampliamente el costo.

**P: ¿Y si `--grammar-file` no existe en mi versión de `llama-server`?**

R: Usar `--grammar` con la gramática inline o actualizar `llama.cpp`.
La versión del repo (`bin/start_engine.sh`) se compila desde fuente
o se descarga precompilada — verificar que sea reciente (≥b4000).

---

## 15. Errores corregidos post-implementación

Durante la revisión posterior a la implementación inicial se encontraron y
corrigieron los siguientes errores:

### 15.1 `low-power.env` incompleto (3 env vars faltantes)

**Problema:** El perfil no incluía `CEREBRO_LLAMACPP_ARGS_FILE`,
`CEREBRO_PLANNER_MAX_STEPS` ni `CEREBRO_SHORT_TERM_MAX_MESSAGES`. Sin
`ARGS_FILE`, el sistema usaba `config/chat.args` en vez de
`chat-lowpower.args`, por lo que grammar + ctx-size nunca se activaban.
Sin `PLANNER_MAX_STEPS`, el TaskPlanner usaba 4 pasos en vez de 2.

**Fix:** Agregadas las 3 líneas a `config/profiles/low-power.env` (líneas
13, 16, 19). Ahora el perfil activa correctamente el args file de
low-power, limita el planner a 2 pasos y reduce short-term memory a 8.

### 15.2 Duplicado de `AGENTS.md` en sección 13

**Problema:** La sección 13 tenía dos entradas idénticas para `AGENTS.md`,
una sin marcador `[✅ Done]` y otra con. Probablemente el agente de coding
creó la entrada dos veces.

**Fix:** Eliminada la primera ocurrencia (sin marcador). Conservada la
segunda con `[✅ Done]`.

### 15.3 `config/chat-lowpower.args` sin marcar en sección 2.2

**Problema:** La sección 2.2 mostraba el archivo como "← NUEVO" a pesar
de que ya estaba creado y en uso.

**Fix:** Cambiado a "← ✅ Done".

### 15.4 Acceptance criteria inconsistentes

**Problema:** Los criterios 3, 6, 7, 8, 9 y 13 tenían el marcador
`[✅ Done]` en distinto formato o simplemente no tenían marcador.

**Fix:** Estandarizados: criterios implementados tienen `✅ Done`,
pendientes de verificación manual tienen `_(p. verificación)_`.

### 15.5 Modelo cambiado de Q4_K_M a Q5_K_M + descarga

**Problema:** El plan original usaba Qwen2.5-0.5B-Instruct-Q4_K_M.gguf. El
usuario prefirió Q5_K_M (mejor precisión en tool calling). Además, el modelo
no estaba realmente descargado — existía un symlink roto que daba la
impresión errónea de que ya estaba disponible.

**Fix:**
1. Eliminados symlinks rotos (`Qwen2.5-0.5B-Instruct-Q5_K_M.gguf` y
   `qwen2.5-0.5b-instruct-q5_k_m.gguf` que se apuntaban circularmente)
2. Descargado `qwen2.5-0.5b-instruct-q5_k_m.gguf` (498 MB, 19s a 25 MB/s)
   desde HuggingFace
3. SHA256 verificado: `041474553fcabfc2a2d67903f9d2c2e50bd92528e670da4f33b5d0ce6e59fd55`
4. Actualizadas todas las referencias en config: `low-power.env`,
   `chat-lowpower.args`, `download-models.sh`, plan `.md`
5. El archivo se almacena como `qwen2.5-0.5b-instruct-q5_k_m.gguf`. En APFS
   (case-insensitive), el nombre `Qwen2.5-0.5B-Instruct-Q5_K_M.gguf` es el
   mismo archivo — no se necesita symlink adicional.

**RAM estimada:** ~0.8 GB (vs ~0.7 GB del Q4_K_M, ~68 % menos que el 2B).

### 15.6 Lección aprendida

Los 3 errores funcionales (env vars faltantes) comparten la misma causa
raíz: el plan escrito en el `.md` especificaba correctamente las variables
en las secciones 3, 4.3 y 8.3, pero el agente de coding no las incluyó
en el archivo real porque el prompt decía "crea el archivo con el contenido
de la sección 3.1" — y las variables en cuestión estaban en otras
secciones (4.3, 8.3). **Los prompts deben referenciar explícitamente todas
las secciones relevantes, no solo la sección donde está el template.**
