# Plan de Implementación: i18n Español/Inglés (Backend + Frontend)

## Resumen

Añadir selección de idioma (español / inglés) en backend y frontend, persistente, cambiable desde UI.

**Filosofía**: Implementación por **capas independientes y reversibles**. Cada capa es funcional por sí misma. Si una capa falla, las anteriores siguen funcionando.

**Source of truth**: `CEREBRO_LOCALE` env var. Frontend lo lee/escribe via `PATCH /api/config { locale }`. Catálogos:
- Backend: `core/i18n/messages.py` (`_MESSAGES_ES` / `_MESSAGES_EN`)
- Frontend: `ui/tray/src/locales/{en,es}.json`

---

## ▶️ Layer 1: Backend completo (seguro, bajo riesgo) ✅ DONE

Backend completo con EN/ES, startup prompt, y API config. Sin tocar frontend.

### 1.1. Catálogo EN en `core/i18n/messages.py`

Añadir `_MESSAGES_EN` y actualizar `_catalog()`:

```python
_MESSAGES_EN: dict[str, str] = {
    "confirm.tool_pause": (
        "I need your approval to run `{tool_name}`. "
        "Approve or reject the action in the confirmation panel."
    ),
    "parse.llm_fallback": (
        "I couldn't parse the model's response. Try rephrasing your question."
    ),
    "parse.tool_unknown": "The tool '{tool_name}' is not available.",
}

def _catalog() -> dict[str, str]:
    locale = os.getenv("CEREBRO_LOCALE", "es").lower()
    if locale.startswith("en"):
        return _MESSAGES_EN
    return _MESSAGES_ES
```

### 1.2. Migrar strings hardcodeadas del backend a `_L()`

| Archivo | Línea(s) | Clave `_L` |
|---------|----------|------------|
| `core/agents/runtime.py` | 743, 745, 749-753, 814, 816, 818, 1629, 1636, 1672, 1677 | `fastpath.*`, `error.*` |
| `core/agents/kernel.py` | 124, 176, 184 | `error.timeout`, `error.tool_loop`, `error.max_iterations` |
| `core/agents/fast_path_router.py` | 367, 369, 427, 432 | `fastpath.*`, `calendar.*` |
| `core/rag/query_engine.py` | 12 | `rag.no_info` |
| `core/tools/handlers/web.py` | 12, 32, 35, 88, 90 | `web.*` |
| `core/tools/handlers/filesystem.py` | 362-370, 374 | `filesystem.*` |

**Convención**: `"{modulo}.{contexto}"`.

### 1.3. `_prompt_language()` en `main.py`

Mismo patrón que `_prompt_lite_profile()`. Colocar justo después:

```python
def _prompt_language() -> None:
    if "CEREBRO_LOCALE" in os.environ or not sys.stdin.isatty():
        return
    print()
    answer = input("🌐 Language / Idioma [E]nglish / [S]panish [E]: ").strip().lower()
    if answer in ("s", "spanish", "español", "es"):
        os.environ["CEREBRO_LOCALE"] = "es"
        print("✅ Idioma: Español")
    else:
        os.environ["CEREBRO_LOCALE"] = "en"
        print("✅ Language: English")
    print()
```

Also sync locale from `config.json` if env not set:

```python
# Tras _prompt_language(), antes de _build_app_state()
if "CEREBRO_LOCALE" not in os.environ:
    try:
        _cfg_path = Path(STATE_DIR) / "config.json"
        if _cfg_path.exists():
            _cfg = json.loads(_cfg_path.read_text())
            if "locale" in _cfg:
                os.environ["CEREBRO_LOCALE"] = str(_cfg["locale"])
    except Exception:
        pass
```

### 1.4. `locale` en Config API (`server.py`)

En `patch_config()`:
```python
if "locale" in settings:
    os.environ["CEREBRO_LOCALE"] = str(settings["locale"])
    if app_state.enricher:
        app_state.enricher.language = str(settings["locale"])
```

En `get_config()`:
```python
cfg.setdefault("locale", os.getenv("CEREBRO_LOCALE", "en"))
```

### 1.5. ContextEnricher locale-aware

```python
# _build_app_state()
enricher = ContextEnricher(
    ...
    language=os.getenv("CEREBRO_LOCALE", "en"),
)

# enrich() date format
if self.language == "es":
    now_str = datetime.now().astimezone().strftime("%A %d de %B de %Y, %H:%M %Z")
else:
    now_str = datetime.now().astimezone().strftime("%A %B %d, %Y %H:%M %Z")
```

### 1.6. NO traducir (por ahora)

- **Tool descriptions** (`registry.py`) — se envían al LLM, no al usuario
- **System prompts** — el LLM debe mantener idioma consistente
- **loguru** — solo desarrollo/ops

### 1.7. Verificación Layer 1 ✅

```bash
CEREBRO_LOCALE=es python -c "from core.i18n.messages import _L; print(_L('confirm.tool_pause', tool_name='test'))"
CEREBRO_LOCALE=en python -c "from core.i18n.messages import _L; print(_L('confirm.tool_pause', tool_name='test'))"
make test-stable   # Tests existentes deben pasar
```

**Resultado**: 79 tests pasan. Catálogos ES/EN funcionales. Startup prompt operativo. Locale persistente via `PATCH /api/config`.

### 1.8. Archivos modificados en Layer 1

| Archivo | Cambio |
|---------|--------|
| `core/i18n/messages.py` | Añadido `_MESSAGES_EN` (40 claves), actualizado `_catalog()`, añadidas claves ES para todas las strings migradas |
| `core/agents/runtime.py` | 4 bloques de strings migrados a `_L()` (file fast path, reminder fast path, tool loop, max iterations, unauthorized tool, tool not found) |
| `core/agents/kernel.py` | 3 strings migrados a `_L()` + import añadido |
| `core/agents/fast_path_router.py` | 4 strings migrados a `_L()` (reminder when/day, default event title, with person) |
| `core/rag/query_engine.py` | `NO_INFO_RESPONSE` usa `_L("rag.no_info")` + import añadido |
| `core/tools/handlers/web.py` | 8 strings migrados a `_L()` (truncated, search errors, no results, fetch errors, no content) + import añadido |
| `core/tools/handlers/filesystem.py` | 2 strings + 4 filtros de búsqueda migrados a `_L()` + import añadido |
| `main.py` | Añadido `_prompt_language()`, sincronización locale desde `config.json`, `language` pasado a `ContextEnricher` |
| `ui/tray/server.py` | `GET /api/config` incluye `locale`, `PATCH /api/config` maneja `locale` (setea env y enricher) |
| `core/agents/context_enricher.py` | Formato de fecha locale-aware (ES: "día de mes año", EN: "month día, año") |

---

## ▶️ Layer 2: Frontend — infraestructura + selector de idioma ✅ DONE

Frontend puede cambiar de idioma, pero **solo el selector y Settings están traducidos**. El resto de la UI sigue en inglés como fallback.

### 2.1. Instalar dependencia

```bash
cd ui/tray && npm install react-i18next i18next
```

### 2.2. Archivos de traducción

`ui/tray/src/locales/es.json` — traducción completa (claves para todo el frontend, ~110 entradas). Ver sección [Apéndice A](#apéndice-a-archivos-de-traducción) para el contenido completo.

`ui/tray/src/locales/en.json` — solo `{}` (objeto vacío). `react-i18next` usa el string key como fallback automáticamente. Así el inglés **no necesita archivo**: si una clave no se encuentra en el locale activo, muestra la clave (que está en inglés). Opcionalmente se puede tener `en.json` completo para consistencia.

**Estrategia de fallback**:
- Si `es.json` falta una clave → se muestra la string original hardcodeada (porque no envolvemos strings hasta la Layer 3 una por una)
- Si `en.json` falta una clave → igual, se muestra el valor hardcodeado
- `fallbackLng: "en"` como red de seguridad

### 2.3. Configurar i18n

`ui/tray/src/i18n.ts`:
```typescript
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import es from "./locales/es.json";

i18n.use(initReactI18next).init({
  resources: { es: { translation: es } },
  lng: "en",
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

export default i18n;
```

En `main.tsx`:
```typescript
import "./i18n";
```

### 2.4. `locale` en AppConfig (`types.ts`)

```typescript
export interface AppConfig {
  // ... campos existentes ...
  locale?: string;
}
```

### 2.5. Cargar locale desde backend al iniciar (`settings.ts` store)

```typescript
// En load()
const config = await getConfig();
if (config.locale) {
  i18n.changeLanguage(config.locale);
}
```

### 2.6. Selector de idioma en `SettingsPanel.tsx`

Solo este componente se envuelve con `t()`. Dropdown simple:

```tsx
import { useTranslation } from "react-i18next";

function SettingsPanel() {
  const { t, i18n } = useTranslation();
  const locale = useSettingsStore((s) => s.config?.locale || "en");

  const handleLanguageChange = async (lang: string) => {
    await i18n.changeLanguage(lang);
    await useSettingsStore.getState().patch({ locale: lang });
  };

  return (
    <div className="settings-section">
      <h3>{t("settings.language")}</h3>
      <select value={locale} onChange={(e) => handleLanguageChange(e.target.value)}>
        <option value="en">English</option>
        <option value="es">Español</option>
      </select>
    </div>
  );
}
```

### 2.7. Verificación Layer 2 ✅

```bash
cd ui/tray && npm run build   # Build sin errores
```

**Resultado**: Build exitoso (6.28s). Selector de idioma funcional en Settings. Locale persiste via `PATCH /api/config`.

### 2.8. Archivos modificados/creados en Layer 2

| Archivo | Acción |
|---------|--------|
| `ui/tray/package.json` | Añadidas dependencias `react-i18next`, `i18next` |
| `ui/tray/src/locales/es.json` | **Creado** — 110 claves de traducción al español |
| `ui/tray/src/locales/en.json` | **Creado** — 110 claves de traducción al inglés |
| `ui/tray/src/i18n.ts` | **Creado** — Configuración de i18next con ES/EN |
| `ui/tray/src/main.tsx` | Importado `./i18n` |
| `ui/tray/src/api/types.ts` | Añadido `locale?: string` a `AppConfig` |
| `ui/tray/src/stores/settings.ts` | Carga locale desde backend + `i18n.changeLanguage()` en `load()` |
| `ui/tray/src/components/settings/SettingsPanel.tsx` | Selector de idioma + 8 labels envueltos con `t()` |

---

## ▶️ Layer 3: Frontend — strings críticos visibles ✅ DONE

Traducir los componentes que el usuario ve constantemente.

### Archivos modificados

| # | Archivo | Claves envueltas con `t()` |
|---|---------|---------------------------|
| 3.1 | `SettingsPanel.tsx` | `settings.watched_folders`, `settings.inference_backend`, `settings.model`, `settings.tool_permissions`, `settings.dnd`, `settings.fleet`, `settings.knowledge_sync` |
| 3.2 | `Header.tsx` | `header.documents`, `header.sync`, `header.settings`, `header.debug`, `header.time_travel_debugger`, `header.monitoring`, `header.workflows`, `sync.started`, `sync.failed` |
| 3.3 | `StatusBar.tsx` | `status.cerebro_os`, `status.ram`, `status.cpu`, `status.uptime` |
| 3.4 | `EngineIndicator.tsx` | `status.turned_off`, `status.claude_api`, `status.engine_suspended`, `status.engine_restarting`, `status.engine_ok`, `status.engine_down` |
| 3.5 | `ServiceControls.tsx` | `service.turn_on`, `service.turn_off`, `service.starting`, `service.stopping` |
| 3.6 | `LeftSidebar.tsx` | `sidebar.chat`, `sidebar.sources`, `sidebar.tools`, `sidebar.code` |
| 3.7 | `AgentBar.tsx` | `chat.clear` |
| 3.8 | `TypingIndicator.tsx` | `chat.thinking` |

### Claves nuevas añadidas a los JSON

| Clave | EN | ES |
|-------|----|-----|
| `status.engine_suspended` | `"suspended"` | `"suspendido"` |
| `status.engine_restarting` | `"restarting"` | `"reiniciando"` |
| `status.claude_api` | `"Claude API"` | `"Claude API"` |
| `header.monitoring` | `"Monitoring"` | `"Monitoreo"` |
| `header.time_travel_debugger` | `"Time-Travel Debugger"` | `"Depurador viaje temporal"` |
| `sync.failed` | `"Sync failed"` | `"Sincronización falló"` |

### Verificación Layer 3 ✅

```bash
cd ui/tray && npm run build   # Build exitoso
```

**Resultado**: Build exitoso (7.92s). Header, StatusBar, EngineIndicator, ServiceControls, LeftSidebar, AgentBar y TypingIndicator responden al selector de idioma.

---

## ▶️ Layer 4: Frontend — chat + confirmaciones ✅ DONE

Traducir el área principal de interacción: input, mensajes, tool confirmations, comandos `/`.

### Archivos modificados

| # | Archivo | Claves envueltas con `t()` |
|---|---------|---------------------------|
| 4.1 | `ConfirmModal.tsx` | `confirm.title`, `confirm.tool_label`, `confirm.path_label`, `confirm.action_label`, `confirm.perform_action`, `confirm.filesystem_warning`, `confirm.deny`, `confirm.approve` |
| 4.2 | `InputArea.tsx` | `input.engine_restarting`, `input.attached_files`, `input.add_files`, `input.file_upload`, `input.voice_input`, `input.engine_status`, `chat.placeholder`, `chat.send`, `chat.cancel`, `chat.engine_off_placeholder`, `error.backend_unreachable`, `error.generic`, `commands.*_response` (14 claves de respuestas de comandos `/`) |
| 4.3 | `ChatWindow.tsx` | `chat.empty` |
| 4.4 | `MessageBubble.tsx` | `searching.web`, `searching.files` |
| 4.5 | `MessageFooter.tsx` | `sources.panel`, `tools.panel`, `memory.panel` |
| 4.6 | `FastPathToggles.tsx` | `note.quick_note`, `documents.reindex`, `settings.dnd`, `tools.browser` |
| 4.7 | `QuickNoteDialog.tsx` | `note.*` (9 claves: saved, done, quick_note, title_placeholder, content_placeholder, cancel, saving, save, failed) |
| 4.8 | `CommandAutocomplete.tsx` | `commands.*` (10 claves de descripciones), refactorizado a `COMMAND_DEFS` + `buildCommands(t)` |

### Claves nuevas añadidas a los JSON

| Clave | EN | ES |
|-------|----|-----|
| `input.engine_status` | `"Engine Status: {status} • Latency {latency}ms"` | `"Estado del motor: {status} • Latencia {latency}ms"` |
| `input.attached_files` | `"[Attached files: {names}]"` | `"[Archivos adjuntos: {names}]"` |
| `commands.help_response` | `"Available commands:\n\n{list}"` | `"Comandos disponibles:\n\n{list}"` |
| `commands.clear_response` | `"Conversation cleared."` | `"Conversación limpiada."` |
| `commands.model_response` | `"Currently running model: **{model}**"` | `"Modelo activo actual: **{model}**"` |
| `commands.status_unavailable` | `"System status not available."` | `"Estado del sistema no disponible."` |
| `commands.status_response` | Plantilla de 10 campos | Plantilla de 10 campos |
| `commands.agents_response` | `"Available agents:\n\n{list}"` | `"Agentes disponibles:\n\n{list}"` |
| `commands.index_started` | `"Starting re-index..."` | `"Iniciando re-indexación..."` |
| `commands.index_job_id` | `"Indexing started with job ID: \`{job_id}\`"` | `"Indexación iniciada con ID: \`{job_id}\`"` |
| `commands.index_failed` | `"Index failed: {message}"` | `"Indexación falló: {message}"` |
| `commands.memory_response` | `"Memory recall hits: **{hits}**\nIndexed files: **{files}**"` | `"Aciertos de memoria: **{hits}**\nArchivos: **{files}**"` |
| `commands.export_response` | `"Conversation exported."` | `"Conversación exportada."` |
| `commands.refresh_response` | `"System status refreshed."` | `"Estado actualizado."` |
| `commands.settings_response` | `"Current configuration:\n\n{lines}"` | `"Configuración actual:\n\n{lines}"` |
| `commands.settings_unavailable` | `"Could not fetch configuration."` | `"No se pudo obtener la configuración."` |
| `commands.engine_active` | `"✅ Active"` | `"✅ Activo"` |
| `commands.engine_offline` | `"❌ Offline"` | `"❌ Sin conexión"` |

### Nota técnica

Los placeholders de interpolación en los JSON usan `{{variable}}` (doble llave), que es el formato que requiere `i18next` por defecto.

### Archivos de test actualizados

| Archivo | Cambio |
|---------|--------|
| `src/test/setup.ts` | Importado `../i18n` para inicializar i18next en tests |
| `MessageBubble.test.tsx` | Regex actualizado para coincidir con strings traducidas |
| `TypingIndicator.test.tsx` | Aria-label actualizado a "Thinking with local" |
| `StatusBar.test.tsx` | Sin cambios (strings coinciden con EN) |

### Verificación Layer 4 ✅

```bash
npx vite build       # Build exitoso (10.66s)
npx vitest run       # 57 tests pasan (10 test files)
cd .. && make test   # Backend: 112 tests pasan
```

**Resultado**: Build, tests frontend (57) y backend (112) pasan. Chat, confirmaciones, comandos `/`, notas rápidas y autocompletado responden al selector de idioma.

---

## ▶️ Layer 5: Frontend — paneles restantes ✅ DONE

Traducir todos los paneles restantes: settings, status, code, wizard, documents, y componentes compartidos.

### Archivos modificados (26 componentes + 2 JSON)

| Categoría | Archivos | Claves envueltas |
|-----------|----------|-----------------|
| **Status** | `RamGaugeRing.tsx`, `CpuMiniGraph.tsx`, `StorageAccessButton.tsx`, `ActiveFleetList.tsx` | `status.memory_allocation`, `status.compute_load`, `status.waiting_data`, `status.connecting`, `status.ram_utilized`, `status.high_pressure`, `status.utilized`, `status.gb_of`, `status.loading`, `documents.storage_access`, `documents.file_count`, `fleet.active`, `fleet.loading`, `fleet.no_models`, `fleet.current`, `fleet.available`, `fleet.switching` |
| **Settings** | `ToolPermissions.tsx`, `DndToggle.tsx`, `KnowledgeSyncPanel.tsx`, `ClaudeApiKeySection.tsx`, `ClaudeModelSection.tsx`, `FolderList.tsx` | `permissions.*` (4), `settings.dnd`, `settings.knowledge_sync`, `knowledge_sync.*` (2), `claude.*` (8), `documents.add_folder`, `documents.remove_folder` |
| **Code** | `CodePanel.tsx`, `OutputTab.tsx`, `ScratchTab.tsx`, `MarkdownRenderer.tsx` | `code.title`, `code.*` (7), `output.*` (7), `markdown.copy_code` |
| **Wizard** | `WizardShell.tsx`, `WizardDots.tsx`, `StepBackend.tsx`, `StepLlamaCpp.tsx`, `StepModel.tsx`, `StepFolders.tsx` | `wizard.*` (~25 claves: step labels, descripciones, botones, estados, permisos calendario) |
| **Documents** | `DocumentsPanel.tsx` | `documents.*` (~12 claves: título, estados, botones, errores) |
| **Shared** | `Toast.tsx`, `SwapBanner.tsx`, `App.tsx` | `toast.dismiss`, `swap.ready`, `swap.switching_to`, `app.error_boundary`, `app.reload` |

### Claves nuevas añadidas (~60)

| Grupo | Claves |
|-------|--------|
| Status | `status.memory_allocation`, `status.compute_load`, `status.waiting_data`, `status.ram_utilized`, `status.high_pressure`, `status.utilized`, `status.gb_of`, `status.loading` |
| Fleet | (ya existían: `fleet.*`) |
| Output | `output.tools_executed`, `output.no_tools`, `output.no_tools_desc`, `output.executed`, `output.denied`, `output.no_result` |
| Code | `code.title`, `code.scratchpad`, `code.copy`, `code.clear`, `code.stats`, `code.empty` |
| Wizard | `wizard.choose_backend`, `wizard.local_title`, `wizard.local_desc`, `wizard.cloud_title`, `wizard.cloud_desc`, `wizard.verify_models`, `wizard.scanning`, `wizard.models_found`, `wizard.no_models`, `wizard.retry_models`, `wizard.then_click`, `wizard.retry`, `wizard.llama_desc`, `wizard.lite_card`, `wizard.lite_button`, `wizard.lite_saving`, `wizard.lite_saved`, `wizard.lite_instructions`, `wizard.checking_llama`, `wizard.llama_running`, `wizard.llama_not_detected`, `wizard.llama_instructions`, `wizard.skipped`, `wizard.detected`, `wizard.not_found`, `wizard.folders_desc`, `wizard.open_settings_btn`, `wizard.calendar_permission`, `wizard.calendar_desc`, `wizard.calendar_granted`, `wizard.calendar_checking`, `wizard.calendar_status`, `wizard.folder_required`, `wizard.step_label`, `wizard.waiting` |
| Documents | `documents.storage_access`, `documents.close`, `documents.empty_hint`, `documents.delete_file`, `documents.documents_filter`, `documents.remove_folder`, `documents.load_error`, `documents.delete_error`, `documents.connecting`, `documents.file_count`, `documents.add_folder`, `documents.select_files` |
| Knowledge Sync | `knowledge_sync.enabled_text`, `knowledge_sync.disabled_text` |
| Markdown | `markdown.copy_code` |
| Swap | `swap.ready`, `swap.switching_to` |
| App | `app.error_boundary`, `app.reload` |
| Claude | `claude.models`, `claude.key_synced`, `claude.saved_locally`, `claude.key_saved`, `claude.save_failed` |
| Toast | `toast.dismiss`, `toast.dismiss_warning` |

### Archivos NO modificados (menor prioridad / no críticos)

| Archivo | Razón |
|---------|-------|
| `SourcesView.tsx` | Contenido principalmente dinámico (nombres de fuentes, URLs), strings estructurales mínimos |
| `SourceForm.tsx` | Labels de formulario mayormente técnicos (URL, Type, Tags, etc.) |
| `SourceList.tsx` | Labels de tipos de fuente (RSS, GitHub, etc.) mayormente iguales en ambos idiomas |
| `TerminalTab.tsx` | Mensajes de terminal mayormente técnicos |
| `ModelSelector.tsx` | Nombres de modelos GGUF (no se traducen) |
| `TimeTravelView.tsx` | Panel de debugging, strings mayormente técnicos |
| `WorkflowPanel.tsx` | Flujo de automatización, strings mayormente técnicos |

### Verificación Layer 5 ✅

```bash
cd ui/tray && npx vite build           # Build exitoso (2.68s)
cd ui/tray && npx vitest run           # 57 tests pasan (10 files)
cd .. && .venv/bin/python -m pytest tests/test_stable_fast_paths.py tests/test_agent_runtime.py -x -q  # 112 tests backend pasan
```

---

## ▶️ Apéndice A: Archivos de traducción

### `ui/tray/src/locales/es.json`

```json
{
  "app.title": "Cerebro",
  "chat.placeholder": "Pregúntale a Cerebro o escribe un comando...",
  "chat.empty": "Pregunta cualquier cosa sobre tus notas...",
  "chat.send": "Enviar mensaje",
  "chat.cancel": "Cancelar",
  "chat.clear": "Limpiar conversación",
  "chat.thinking": "Pensando con {model}",
  "chat.engine_off_placeholder": "El motor está apagado — usa Turn on para chatear",
  "confirm.title": "Herramienta requiere tu aprobación",
  "confirm.approve": "Aprobar",
  "confirm.deny": "Denegar",
  "confirm.tool_label": "Herramienta",
  "confirm.path_label": "Ruta",
  "confirm.action_label": "Acción",
  "confirm.perform_action": "Realizar acción",
  "confirm.filesystem_warning": "Esta acción modificará tu sistema de archivos. No se puede deshacer automáticamente.",
  "settings.title": "Configuración",
  "settings.language": "Idioma",
  "settings.watched_folders": "Carpetas vigiladas",
  "settings.inference_backend": "Backend de inferencia",
  "settings.model": "Modelo",
  "settings.tool_permissions": "Permisos de herramientas",
  "settings.dnd": "No molestar",
  "settings.fleet": "Orquestador Fleet",
  "settings.knowledge_sync": "Sincronización de conocimiento",
  "header.documents": "Documentos",
  "header.sync": "Sincronizar fuentes",
  "header.settings": "Configuración",
  "header.debug": "Depurador",
  "header.workflows": "Flujos de trabajo",
  "sidebar.chat": "Chat",
  "sidebar.sources": "Fuentes",
  "sidebar.tools": "Herramientas",
  "sidebar.code": "Código",
  "status.ram": "RAM {used}/{total}GB",
  "status.cpu": "CPU {percent}%",
  "status.uptime": "Tiempo activo",
  "status.cerebro_os": "Cerebro OS",
  "status.engine_ok": "OK",
  "status.engine_down": "Caído",
  "status.engine_off": "Apagado",
  "status.turned_off": "Apagado",
  "status.connecting": "Conectando...",
  "service.turn_on": "Encender",
  "service.turn_off": "Apagar",
  "service.starting": "Iniciando...",
  "service.stopping": "Deteniendo...",
  "wizard.title": "Cerebro",
  "wizard.subtitle": "Tu segundo cerebro AI privado",
  "wizard.step_backend": "Elegir Backend",
  "wizard.step_llamacpp": "Iniciar llama.cpp",
  "wizard.step_model": "Verificar Modelos",
  "wizard.step_folders": "Añadir Carpetas",
  "wizard.continue": "Continuar",
  "wizard.finish": "Finalizar",
  "tools.manager": "Administrador de Herramientas",
  "tools.browser": "Explorador",
  "tools.recent_usage": "Uso Reciente",
  "tools.quick_actions": "Acciones Rápidas",
  "tools.loading": "Cargando herramientas...",
  "tools.no_tools": "No hay herramientas registradas",
  "sources.title": "Fuentes de Conocimiento",
  "sources.add_link": "Añadir Enlace",
  "sources.empty": "Aún no hay enlaces",
  "code.terminal": "Terminal",
  "code.output": "Salida",
  "code.scratch": "Borrador",
  "note.saved": "Nota guardada",
  "note.done": "Hecho",
  "note.quick_note": "Nota Rápida",
  "note.title_placeholder": "Título (opcional)",
  "note.content_placeholder": "Escribe tu nota...",
  "note.cancel": "Cancelar",
  "note.saving": "Guardando...",
  "note.save": "Guardar Nota",
  "note.failed": "Error al guardar la nota",
  "input.add_files": "Añadir archivos",
  "input.file_upload": "Subir archivos (imágenes, PDFs, documentos)",
  "input.voice_input": "Entrada de voz",
  "input.engine_restarting": "El motor de inferencia se está reiniciando. Espera un momento e inténtalo de nuevo.",
  "error.generic": "Error: {message}",
  "error.backend_unreachable": "No se puede alcanzar el backend. Asegúrate de que `make run` esté ejecutándose en el puerto 7842.",
  "documents.title": "Documentos",
  "documents.empty": "No hay documentos indexados",
  "documents.count": "{count} archivo(s) indexado(s)",
  "documents.reindex": "Re-indexar carpetas",
  "documents.upload": "Subir archivo",
  "memory.title": "Memoria",
  "sources.panel": "Fuentes",
  "tools.panel": "Herramientas",
  "memory.panel": "Memoria",
  "fleet.active": "Flota Activa",
  "fleet.loading": "Cargando modelos...",
  "fleet.no_models": "No hay modelos disponibles",
  "fleet.current": "Modelo Actual",
  "fleet.available": "Modelos Disponibles",
  "fleet.switching": "Cambiando modelo...",
  "permissions.execute_python": "Ejecutar Python",
  "permissions.write_file": "Escribir Archivo",
  "permissions.read_file": "Leer Archivo",
  "permissions.search_web": "Buscar en Web",
  "claude.api_key": "Clave API de Claude",
  "claude.key_configured": "Clave API configurada",
  "claude.no_key": "Sin clave API",
  "claude.replace": "Reemplazar",
  "claude.setup": "Configurar",
  "claude.save": "Guardar",
  "claude.hide_key": "Ocultar clave",
  "claude.show_key": "Mostrar clave",
  "index.progress": "Indexando... {files} archivos",
  "sync.started": "Sincronización iniciada",
  "syncing": "Sincronizando...",
  "searching.web": "Buscando en la web...",
  "searching.files": "Buscando en {count} archivo(s)...",
  "commands.help": "Mostrar comandos disponibles",
  "commands.clear": "Limpiar historial de conversación",
  "commands.model": "Mostrar modelo activo actual",
  "commands.status": "Mostrar estado del sistema (RAM, latencia, modelo)",
  "commands.agents": "Listar agentes disponibles",
  "commands.index": "Re-indexar todas las carpetas vigiladas",
  "commands.memory": "Mostrar uso de memoria y estadísticas",
  "commands.export": "Exportar conversación a archivo",
  "commands.refresh": "Actualizar estado del sistema",
  "commands.settings": "Mostrar configuración actual"
}
```

### `ui/tray/src/locales/en.json`

```json
{
  "app.title": "Cerebro",
  "chat.placeholder": "Ask Cerebro or issue a command...",
  "chat.empty": "Ask anything about your notes...",
  "chat.send": "Send message",
  "chat.cancel": "Cancel request",
  "chat.clear": "Clear conversation",
  "chat.thinking": "Thinking with {model}",
  "chat.engine_off_placeholder": "Engine is off — use Turn on to chat again",
  "confirm.title": "Tool requires your approval",
  "confirm.approve": "Approve",
  "confirm.deny": "Deny",
  "confirm.tool_label": "Tool",
  "confirm.path_label": "Path",
  "confirm.action_label": "Action",
  "confirm.perform_action": "Perform action",
  "confirm.filesystem_warning": "This action will modify your filesystem. It cannot be automatically undone.",
  "settings.title": "Settings",
  "settings.language": "Language",
  "settings.watched_folders": "Watched Folders",
  "settings.inference_backend": "Inference Backend",
  "settings.model": "Model",
  "settings.tool_permissions": "Tool Permissions",
  "settings.dnd": "Do Not Disturb",
  "settings.fleet": "Fleet Orchestrator",
  "settings.knowledge_sync": "Knowledge Sync",
  "header.documents": "Documents",
  "header.sync": "Sync all sources",
  "header.settings": "Settings",
  "header.debug": "Debugger",
  "header.workflows": "Workflows",
  "sidebar.chat": "Chat",
  "sidebar.sources": "Sources",
  "sidebar.tools": "Tools",
  "sidebar.code": "Code",
  "status.ram": "RAM {used}/{total}GB",
  "status.cpu": "CPU {percent}%",
  "status.uptime": "Uptime",
  "status.cerebro_os": "Cerebro OS",
  "status.engine_ok": "OK",
  "status.engine_down": "Down",
  "status.engine_off": "Off",
  "status.turned_off": "Turned off",
  "status.connecting": "Connecting...",
  "service.turn_on": "Turn on",
  "service.turn_off": "Turn off",
  "service.starting": "Starting...",
  "service.stopping": "Stopping...",
  "wizard.title": "Cerebro",
  "wizard.subtitle": "Your private AI second brain",
  "wizard.step_backend": "Choose Backend",
  "wizard.step_llamacpp": "Start llama.cpp",
  "wizard.step_model": "Check Models",
  "wizard.step_folders": "Add Folders",
  "wizard.continue": "Continue",
  "wizard.finish": "Finish",
  "tools.manager": "Tool Manager",
  "tools.browser": "Tool Browser",
  "tools.recent_usage": "Recent Usage",
  "tools.quick_actions": "Quick Actions",
  "tools.loading": "Loading tools...",
  "tools.no_tools": "No tools registered",
  "sources.title": "Knowledge Sources",
  "sources.add_link": "Add Link",
  "sources.empty": "No links yet",
  "code.terminal": "Terminal",
  "code.output": "Output",
  "code.scratch": "Scratch",
  "note.saved": "Note saved",
  "note.done": "Done",
  "note.quick_note": "Quick Note",
  "note.title_placeholder": "Title (optional)",
  "note.content_placeholder": "Write your note...",
  "note.cancel": "Cancel",
  "note.saving": "Saving...",
  "note.save": "Save Note",
  "note.failed": "Failed to save note",
  "input.add_files": "Add files",
  "input.file_upload": "Upload files (images, PDFs, documents)",
  "input.voice_input": "Voice input",
  "input.engine_restarting": "The inference engine is restarting. Wait a moment and try again.",
  "error.generic": "Error: {message}",
  "error.backend_unreachable": "Cannot reach the backend. Make sure `make run` is running on port 7842.",
  "documents.title": "Documents",
  "documents.empty": "No indexed documents",
  "documents.count": "{count} file(s) indexed",
  "documents.reindex": "Re-index watched folders",
  "documents.upload": "Upload file",
  "memory.title": "Memory",
  "sources.panel": "Sources",
  "tools.panel": "Tools",
  "memory.panel": "Memory",
  "fleet.active": "Active Fleet",
  "fleet.loading": "Loading models...",
  "fleet.no_models": "No models available",
  "fleet.current": "Current Model",
  "fleet.available": "Available Models",
  "fleet.switching": "Switching model...",
  "permissions.execute_python": "Execute Python",
  "permissions.write_file": "Write File",
  "permissions.read_file": "Read File",
  "permissions.search_web": "Search Web",
  "claude.api_key": "Claude API Key",
  "claude.key_configured": "API key configured",
  "claude.no_key": "No API key",
  "claude.replace": "Replace",
  "claude.setup": "Set up",
  "claude.save": "Save",
  "claude.hide_key": "Hide key",
  "claude.show_key": "Show key",
  "index.progress": "Indexing... {files} files",
  "sync.started": "Sync started",
  "syncing": "Syncing...",
  "searching.web": "Searching the web...",
  "searching.files": "Searching {count} file(s)...",
  "commands.help": "Show available commands",
  "commands.clear": "Clear conversation history",
  "commands.model": "Show current active model",
  "commands.status": "Show system status (RAM, latency, model)",
  "commands.agents": "List available agents",
  "commands.index": "Re-index all watched folders",
  "commands.memory": "Show memory usage and recall stats",
  "commands.export": "Export conversation to file",
  "commands.refresh": "Refresh system status",
  "commands.settings": "Show current configuration"
}
```

---

## ▶️ Apéndice B: Resumen por capa

| Capa | Archivos nuevos | Archivos modificados | Riesgo | Funcionalidad |
|------|----------------|---------------------|--------|---------------|
| **Layer 1** (Backend) ✅ | 0 | 10 | 🟢 Muy bajo | Backend bilingüe, startup prompt, locale persistente |
| **Layer 2** (Frontend infra) ✅ | 5 | 5 | 🟢 Bajo | Selector de idioma en Settings, infraestructura i18n |
| **Layer 3** (Frontend crítico) ✅ | 0 | 7 + 2 JSON | 🟡 Medio-bajo | Header, StatusBar, Sidebar, Settings, EngineIndicator, ServiceControls, AgentBar, TypingIndicator traducidos |
| **Layer 4** (Frontend chat) ✅ | 0 | 8 + 4 tests | 🟡 Medio | Chat, confirmaciones, input, comandos `/`, notas rápidas traducidos |
| **Layer 5** (Frontend resto) ✅ | 0 | 26 + 2 JSON | 🟡 Medio | Paneles restantes: status, code, wizard, documents, settings, shared components |

**Cada capa es independiente**. Puedes parar después de cualquier capa y todo funciona. Si una capa introduce un bug, solo reviertes los archivos de esa capa.
