# Plan de Implementación: i18n Español/Inglés (Backend + Frontend)

## Resumen

Añadir selección de idioma (español / inglés) en backend y frontend, persistente, cambiable desde UI.

**Filosofía**: Implementación por **capas independientes y reversibles**. Cada capa es funcional por sí misma. Si una capa falla, las anteriores siguen funcionando.

**Source of truth**: `CEREBRO_LOCALE` env var. Frontend lo lee/escribe via `PATCH /api/config { locale }`. Catálogos:
- Backend: `core/i18n/messages.py` (`_MESSAGES_ES` / `_MESSAGES_EN`)
- Frontend: `ui/tray/src/locales/{en,es}.json`

---

## ▶️ Layer 1: Backend completo (seguro, bajo riesgo)

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

### 1.7. Verificación Layer 1

```bash
CEREBRO_LOCALE=es python -c "from core.i18n.messages import _L; print(_L('confirm.tool_pause', tool_name='test'))"
CEREBRO_LOCALE=en python -c "from core.i18n.messages import _L; print(_L('confirm.tool_pause', tool_name='test'))"
make test-stable   # Tests existentes deben pasar
```

---

## ▶️ Layer 2: Frontend — infraestructura + selector de idioma

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

### 2.7. Verificación Layer 2

```bash
cd ui/tray && npm run build   # Build sin errores
```

Test manual:
1. Frontend arranca → se ve todo en inglés (fallback)
2. Ir a Settings → selector de idioma funciona
3. Cambiar a Español → solo el selector se ve en español, el resto en inglés
4. Recargar → persiste
5. `GET /api/config` → devuelve `locale`

---

## ▶️ Layer 3: Frontend — strings críticos visibles

Traducir los componentes que el usuario ve constantemente. Si algo falla aquí, solo afecta a estos archivos.

### Archivos a modificar (en orden)

| # | Archivo | Claves | Riesgo |
|---|---------|--------|--------|
| 3.1 | `SettingsPanel.tsx` | `settings.title`, `settings.watched_folders`, `settings.inference_backend`, `settings.model`, `settings.tool_permissions`, `settings.dnd`, `settings.fleet`, `settings.knowledge_sync` | Bajo — ya tiene `t()` del Layer 2 |
| 3.2 | `Header.tsx` | `header.documents`, `header.sync`, `header.settings`, `header.debug`, `header.workflows` | Bajo |
| 3.3 | `StatusBar.tsx` | `status.cerebro_os`, `status.ram`, `status.cpu`, `status.uptime` | Bajo |
| 3.4 | `EngineIndicator.tsx` | `status.engine_ok`, `status.engine_down`, `status.engine_off`, `status.turned_off` | Bajo |
| 3.5 | `ServiceControls.tsx` | `service.turn_on`, `service.turn_off`, `service.starting`, `service.stopping` | Bajo |
| 3.6 | `LeftSidebar.tsx` | `sidebar.chat`, `sidebar.sources`, `sidebar.tools`, `sidebar.code` | Bajo |
| 3.7 | `AgentBar.tsx` | `chat.clear` | Bajo |
| 3.8 | `TypingIndicator.tsx` | `chat.thinking` | Bajo |

### Verificación Layer 3

```bash
cd ui/tray && npm run build
```

El Header, StatusBar, sidebar, etc. ahora cambian de idioma al seleccionar. Si algo está mal, solo un componente se rompe y es obvio cuál.

---

## ▶️ Layer 4: Frontend — chat + confirmaciones

Traducir el área principal de interacción: input, mensajes, tool confirmations.

### Archivos a modificar

| # | Archivo | Claves | Riesgo |
|---|---------|--------|--------|
| 4.1 | `ConfirmModal.tsx` | `confirm.*` (~8) | Medio — flujo crítico |
| 4.2 | `InputArea.tsx` | `chat.placeholder`, `chat.send`, `chat.cancel`, `input.*`, `error.backend_unreachable`, `commands.*`, `chat.engine_off_placeholder` | Medio |
| 4.3 | `ChatWindow.tsx` | `chat.empty` | Bajo |
| 4.4 | `MessageBubble.tsx` | `searching.web`, `searching.files` | Bajo |
| 4.5 | `MessageFooter.tsx` | `sources.panel`, `tools.panel`, `memory.panel` | Bajo |
| 4.6 | `FastPathToggles.tsx` | `Quick Note`, `Index Now`, `Focus Mode`, `Web Search` | Bajo |
| 4.7 | `QuickNoteDialog.tsx` | `note.*` (~10) | Bajo |
| 4.8 | `CommandAutocomplete.tsx` | `commands.*` (~10) | Bajo |

### Verificación Layer 4

Test manual completo del chat: enviar mensaje, recibir respuesta, confirmar tool, comandos `/`. Todo debe verse en el idioma seleccionado.

---

## ▶️ Layer 5: Frontend — paneles restantes

Traducir sources, tools, code, wizard, debug, workflows, documents.

### Archivos a modificar

| # | Archivo | Claves |
|---|---------|--------|
| 5.1 | `SourcesView.tsx` | `sources.*` |
| 5.2 | `SourceForm.tsx` | formulario |
| 5.3 | `SourceList.tsx` | listado |
| 5.4 | `ToolsPanel.tsx` | `tools.*` |
| 5.5 | `CodePanel.tsx` | `code.*` |
| 5.6 | `TerminalTab.tsx` | ~10 |
| 5.7 | `OutputTab.tsx` | ~8 |
| 5.8 | `ScratchTab.tsx` | ~5 |
| 5.9 | `WizardShell.tsx` + steps | `wizard.*` |
| 5.10 | `DocumentsPanel.tsx` | `documents.*` |
| 5.11 | `TimeTravelView.tsx` | ~10 |
| 5.12 | `WorkflowPanel.tsx` | ~10 |
| 5.13 | `RamGaugeRing.tsx` | ~3 |
| 5.14 | `CpuMiniGraph.tsx` | ~2 |
| 5.15 | `StorageAccessButton.tsx` | ~2 |
| 5.16 | `ActiveFleetList.tsx` | `fleet.*` |
| 5.17 | `ToolPermissions.tsx` | `permissions.*` |
| 5.18 | `DndToggle.tsx` | `settings.dnd` |
| 5.19 | `ClaudeApiKeySection.tsx` | `claude.*` |
| 5.20 | `ModelSelector.tsx` | ~5 |
| 5.21 | `FolderList.tsx` | ~2 |
| 5.22 | `Toast.tsx` | ~1 |
| 5.23 | `SwapBanner.tsx` | ~2 |
| 5.24 | `MarkdownRenderer.tsx` | ~2 |
| 5.25 | `App.tsx` | ~2 (ErrorBoundary) |

### Verificación Layer 5

Navegar por todos los paneles y pantallas, confirmar que se ve en ambos idiomas.

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
| **Layer 1** (Backend) | 0 | ~8 | 🟢 Muy bajo | Backend bilingüe, startup prompt, locale persistente |
| **Layer 2** (Frontend infra) | 4 | ~5 | 🟢 Bajo | Selector de idioma en Settings, infraestructura i18n |
| **Layer 3** (Frontend crítico) | 0 | ~8 | 🟡 Medio-bajo | Header, StatusBar, Sidebar, Settings traducidos |
| **Layer 4** (Frontend chat) | 0 | ~8 | 🟡 Medio | Chat, confirmaciones, input traducidos |
| **Layer 5** (Frontend resto) | 0 | ~25 | 🟡 Medio | Paneles restantes (sources, tools, code, wizard, etc.) |

**Cada capa es independiente**. Puedes parar después de cualquier capa y todo funciona. Si una capa introduce un bug, solo reviertes los archivos de esa capa.
