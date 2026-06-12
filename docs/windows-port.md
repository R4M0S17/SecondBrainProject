# Windows Port — Estrategia de Migración

Guía detallada para que Cerebro funcione nativamente en Windows 10/11. No busca emular macOS APIs vía WSL2 — el objetivo es un port nativo (PowerShell + APIs de Windows).

---

## Resumen de Esfuerzo

| Componente | Líneas macOS | Estrategia | Esfuerzo |
|---|---|---|---|
| Desktop Automation (CGEventTap) | ~360 | Reemplazar con UIA/PyWinAuto | 3-4 días |
| AppleScript Workflows | ~280 | Reemplazar con PowerShell + UIA | 2 días |
| Calendar (Apple Calendar) | ~700 | Usar ICS + Google Calendar API | 2-3 días |
| macOS Apps (Notes/Spotlight/Notify) | ~210 | Reemplazar con Windows equivalentes | 2-3 días |
| Calendar Permission Probe | ~75 | Stub (no aplica en Windows) | 0.5 día |
| Finder Trash | ~10 | `send2trash` library | 0.5 día |
| Shell scripts / Rust launcher | ~460 | PowerShell + bat | 1 día |
| lsof / pkill / bash calls | ~40 | netstat / taskkill / cmd | 0.5 día |
| Platform.gpu_backend probe | ~10 | CUDA/DirectML detection | 0.5 día |
| Tauri .icns / titleBarStyle | ~3 | Condicional en build | 0.5 día |
| ~/Desktop default paths | ~30 | Usar `%USERPROFILE%` | 0.5 día |
| MLX backend | ~30 | Ya gateado, no-op en Windows | 0 día |

**Total estimado: ~12-15 días hábiles** para feature parity completa.

---

## Tabla de Contenidos

- [Fase 0: Infraestructura Base](#fase-0-infraestructura-base)
- [Fase 1: Calendar Backend](#fase-1-calendar-backend)
- [Fase 2: macOS Apps → Windows Equivalents](#fase-2-macos-apps--windows-equivalents)
- [Fase 3: Desktop Automation](#fase-3-desktop-automation)
- [Fase 4: Filesystem & Trash](#fase-4-filesystem--trash)
- [Fase 5: Shell Scripts → PowerShell](#fase-5-shell-scripts--powershell)
- [Fase 6: Tauri/Rust Adjustments](#fase-6-taurirust-adjustments)
- [Fase 7: Config & Defaults](#fase-7-config--defaults)
- [Fase 8: GPU Detection](#fase-8-gpu-detection)
- [Fase 9: Testing](#fase-9-testing)
- [Appendix A: Dependency Map](#appendix-a-dependency-map)
- [Appendix B: API Equivalence Table](#appendix-b-api-equivalence-table)

---

## Fase 0: Infraestructura Base

### 0.1 Python Dependencies

Agregar a `pyproject.toml` bajo `[project.optional-dependencies]`:

```toml
[project.optional-dependencies]
windows = [
    "pywin32>=306",          # COM, Windows API
    "winsdk>=1.0.0",         # Windows SDK bindings (calendar, contacts)
    "send2trash>=1.8.0",     # Mover a papelera en lugar de osascript
    "pywinauto>=0.6.8",      # Desktop automation (UIA)
    "python-dateutil>=2.8",  # Zona horaria Windows
]

dev = [
    "pytest-mock>=3.10",
    # ...existing deps...
]
```

### 0.2 Platform Detection Utility

Crear `core/inference/platform_win.py` — extiende la detección para Windows:

```python
"""Platform detection — cross-platform (macOS + Windows)."""

from __future__ import annotations

import platform
import sys

import psutil


def is_apple_silicon() -> bool:
    return sys.platform == "darwin" and platform.machine() == "arm64"


def mlx_available() -> bool:
    """MLX is Apple Silicon-only."""
    if platform.system() != "Darwin":
        return False
    if not is_apple_silicon():
        return False
    # ...rest...


def is_windows() -> bool:
    return platform.system() == "Windows"


def gpu_backend() -> str:
    """Detect available GPU backend: metal|cuda|directml|none."""
    if is_apple_silicon():
        return "metal"
    if is_windows():
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            # DirectML detection
            import onnxruntime
            if "DmlExecutionProvider" in onnxruntime.get_available_providers():
                return "directml"
        except ImportError:
            pass
    return "none"
```

### 0.3 Path Utilities

Windows usa `%USERPROFILE%` en vez de `~`. Crear helper en `core/utils/paths.py`:

```python
"""Cross-platform path resolution."""

from __future__ import annotations

import os
from pathlib import Path


def expand_user(path: str) -> Path:
    """Like os.path.expanduser but Windows-aware."""
    if path.startswith("~"):
        home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
        return Path(home) / Path(path[1:]).relative_to("/") if path[1:].startswith("/") else Path(home, path[1:])
    return Path(path).expanduser()


def default_desktop() -> Path:
    """Return path to user Desktop folder."""
    if os.name == "nt":
        return Path(os.environ["USERPROFILE"]) / "Desktop"
    return Path.home() / "Desktop"


def cerebro_data_dir() -> Path:
    """Return ~/.cerebro or %USERPROFILE%\.cerebro."""
    home = os.environ.get("USERPROFILE") if os.name == "nt" else str(Path.home())
    return Path(home) / ".cerebro"
```

Luego reemplazar todos los `os.path.expanduser("~/...")` y `Path("~/...")` con estos helpers.

**Archivos a modificar** (~12 archivos):
- `main.py:51-53,74` — CEREBRO_DB, CEREBRO_STATE, CEREBRO_FILES_PATH
- `ui/tray/server.py:282,290` — paths del servidor
- `core/agents/file_write_fast_path.py:184` — default write root
- `core/agents/file_search_fast_path.py:74,78` — path de búsqueda
- `core/tools/handlers/calendar.py:37` — CEREBRO_ICS
- `core/agents/context_enricher.py:113` — .ics path
- `core/agents/calendar_fast_path.py:127` — .ics path
- `core/cache/stores.py:16` — cache.db
- `core/cache/embedding_cache.py:27,217` — cache db
- `core/inference/fleet/model_registry.py:75,88,101,114` — models dir
- `ui/tray/wizard.py:31` — data dir

---

## Fase 1: Calendar Backend

### Estado Actual

`integrations/calendar_reader.py` (1143 líneas) tiene dos backends:
- `ICalBackend`: lee archivos `.ics` vía `icalendar` library ✅ **cross-platform**
- `AppleCalendarBackend`: JXA/AppleScript para Apple Calendar ❌ **macOS only**

El `CalendarReader` facade alterna entre ambos según `use_apple_calendar` config.

### Estrategia

**Windows no tiene Apple Calendar.** Soluciones:

| Opción | Esfuerzo | Pros | Contras |
|---|---|---|---|
| A. Solo ICS backend | 0.5 día | Cero dependencias Windows | No hay calendario nativo, el usuario debe exportar .ics |
| B. Outlook COM API | 2-3 días | Calendario nativo | Solo si el usuario tiene Outlook |
| C. Windows Calendar API | 2-3 días | App Calendar de Windows 10/11 | API limitada, requiere UWP |
| D. Google Calendar API | 2-3 días | Universal, cloud | Requiere OAuth setup |

**Recomendación: A + B + D.** ICS como fallback universal, Outlook como primary en Windows, Google Calendar como opcional.

### Plan de Implementación

#### 1.1 Refactor CalendarReader para Plugins

Crear `integrations/calendar_backends/` con estructura:

```
integrations/calendar_backends/
  __init__.py          # CalendarBackend abstract base
  ics.py               # ICalBackend (ya existe, mover)
  outlook.py           # OutlookCalendarBackend (nuevo)
  google.py            # GoogleCalendarBackend (nuevo)
  apple.py             # AppleCalendarBackend (existente, macOS only)
```

#### 1.2 OutlookCalendarBackend

```python
"""Windows Outlook Calendar backend via pywin32 COM."""

from __future__ import annotations

from datetime import datetime, timedelta, tzinfo
from typing import Any

from integrations.calendar_reader import BackendResult, CalendarEvent


class OutlookCalendarBackend:
    """Read/write Windows Outlook Calendar via COM."""

    def __init__(self) -> None:
        self._app: Any | None = None

    def _ensure_app(self) -> None:
        if self._app is None:
            import win32com.client
            self._app = win32com.client.Dispatch("Outlook.Application")
            self._ns = self._app.GetNamespace("MAPI")
            self._calendar = self._ns.GetDefaultFolder(9)  # olFolderCalendar

    def get_upcoming(self, hours_ahead: int = 24) -> BackendResult:
        self._ensure_app()
        now = datetime.now()
        end = now + timedelta(hours=hours_ahead)
        items = self._calendar.Items
        items.Sort("[Start]")
        items.IncludeRecurrences = True
        # Filter by date range
        restrict = f"[Start] >= '{now.strftime('%m/%d/%Y %H:%M')}' AND [Start] <= '{end.strftime('%m/%d/%Y %H:%M')}'"
        filtered = items.Restrict(restrict)
        events = []
        for item in filtered:
            events.append(CalendarEvent(
                title=item.Subject or "(sin título)",
                start=item.Start,
                end=item.End,
                description=item.Body or "",
                location=item.Location or "",
            ))
        return BackendResult(events=events, status="ok")

    def create_event(self, title: str, start: datetime, duration_mins: int = 60, description: str = "") -> str:
        self._ensure_app()
        appointment = self._calendar.Items.Add()
        appointment.Subject = title
        appointment.Start = start
        appointment.End = start + timedelta(minutes=duration_mins)
        appointment.Body = description
        appointment.Save()
        return f"Evento creado: '{title}'"

    def delete_by_title(self, title: str) -> str:
        self._ensure_app()
        items = self._calendar.Items
        items.Sort("[Start]")
        for item in items:
            if item.Subject == title:
                item.Delete()
                return f"Evento eliminado: '{title}'"
        return f"No se encontró evento con título '{title}'"
```

#### 1.3 CalendarReader Facade Update

```python
class CalendarReader:
    """Cross-platform calendar facade."""

    def __init__(self, ics_path: str, use_apple: bool = False, use_outlook: bool = False):
        self._ics = ICalBackend(ics_path)
        self._apple = AppleCalendarBackend() if use_apple else None
        self._outlook = OutlookCalendarBackend() if use_outlook else None

    async def get_upcoming(self, hours_ahead: int = 24) -> BackendResult:
        if self._outlook:
            return await asyncio.to_thread(self._outlook.get_upcoming, hours_ahead)
        if self._apple:
            return await self._apple.get_upcoming_events_v2(hours_ahead)
        return self._ics.get_upcoming(hours_ahead)
```

#### 1.4 Config Update

En `config/settings.toml`:

```toml
[calendar]
ics_path = ""
backend = "auto"       # "auto" | "ics" | "outlook" | "apple" | "google"
use_apple_calendar = false
use_outlook = false
```

En `config/settings.toml`, el valor `use_apple_calendar = false` en Windows ya es correcto.

#### 1.5 macOS Permission Probe Stub

`core/observability/macos_perms.py` ya retorna `"not_macos"` cuando `platform.system() != "Darwin"`. **No requiere cambios.**

**Archivos a modificar:**
- `integrations/calendar_reader.py` — refactor mayor
- `integrations/calendar_backends/outlook.py` — nuevo
- `core/tools/handlers/calendar.py` — actualizar imports y lógica de backend
- `core/agents/context_enricher.py:116` — actualizar `use_apple_calendar` flag
- `config/settings.toml` — sección calendar

---

## Fase 2: macOS Apps → Windows Equivalents

### Estado Actual

`integrations/macos_apps.py` (208 líneas) tiene 4 funciones macOS-only:
- `spotlight_search(query)` → `mdfind`
- `create_note(title, body, folder)` → Apple Notes via JXA
- `search_notes(query)` → Apple Notes via JXA
- `send_notification(title, message)` → `display notification` AppleScript

### Estrategia

Crear `integrations/windows_apps.py` con equivalentes funcionales, y un facade que rutee según `platform.system()`.

#### 2.1 Windows Apps Module

```python
"""Windows app integrations — Search, Sticky Notes, notifications."""

from __future__ import annotations

import os
import subprocess
import platform
from pathlib import Path

from loguru import logger


def _is_windows() -> bool:
    return platform.system() == "Windows"


def file_search(query: str, max_results: int = 10) -> str:
    """Search filesystem via Windows Search/indexer (replaces Spotlight)."""
    if not _is_windows():
        return "Windows file search is only available on Windows."

    try:
        # Use PowerShell for fast file search
        ps_script = f"""
            Get-ChildItem -Recurse -ErrorAction SilentlyContinue |
            Where-Object {{ $_.Name -like '*{query}*' }} |
            Select-Object -First {max_results} FullName |
            ForEach-Object {{ $_.FullName }}
        """
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            return f"Error searching files: {result.stderr.strip()}"

        paths = [p for p in result.stdout.strip().splitlines() if p]
        if not paths:
            return f"No files found matching '{query}'"
        return f"Files matching '{query}' ({len(paths)} found):\n" + "\n".join(f"  {p}" for p in paths[:max_results])

    except subprocess.TimeoutExpired:
        return "File search timed out"
    except Exception as exc:
        return f"Error searching files: {exc}"
```

#### 2.2 Windows Search via Everything SDK (Opcional)

Para búsqueda instantánea tipo Spotlight, integrar [voidtools Everything](https://www.voidtools.com/):

```python
def everything_search(query: str, max_results: int = 10) -> str:
    """Search via Everything SDK (much faster than Windows Search)."""
    es_path = r"C:\Program Files\Everything\es.exe"
    if not Path(es_path).exists():
        return file_search(query, max_results)  # fallback

    try:
        result = subprocess.run(
            [es_path, "-n", str(max_results), query],
            capture_output=True, text=True, timeout=10
        )
        paths = [p for p in result.stdout.strip().splitlines() if p]
        if not paths:
            return f"No results for '{query}'"
        return f"Search results for '{query}' ({len(paths)} found):\n" + "\n".join(f"  {p}" for p in paths[:max_results])
    except Exception:
        return file_search(query, max_results)
```

#### 2.3 Replace create_note / search_notes

Windows no tiene Apple Notes. Alternativas:

```python
def create_note(title: str, body: str, folder: str = "Notes") -> str:
    """Create a note in Windows Sticky Notes or a .txt file."""
    if not _is_windows():
        return f"Sticky Notes is only available on Windows. Would have created: '{title}'"

    try:
        # Save as .txt in a notes folder (Windows Sticky Notes has no CLI API)
        notes_dir = Path(os.environ["USERPROFILE"]) / "CerebroNotes"
        notes_dir.mkdir(exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)
        note_path = notes_dir / f"{safe_name}.txt"
        note_path.write_text(body, encoding="utf-8")
        return f"Note created: '{title}' → {note_path}"
    except Exception as exc:
        return f"Error creating note: {exc}"


def search_notes(query: str, max_results: int = 10) -> str:
    """Search notes in CerebroNotes folder."""
    if not _is_windows():
        return "Notes search is only available on Windows."

    notes_dir = Path(os.environ.get("USERPROFILE", "")) / "CerebroNotes"
    if not notes_dir.exists():
        return "No notes folder found."

    results = []
    for f in notes_dir.glob("*.txt"):
        try:
            content = f.read_text(encoding="utf-8")
            if query.lower() in f.stem.lower() or query.lower() in content.lower():
                results.append((f.stem, content[:200]))
        except Exception:
            continue

    if not results:
        return f"No notes matching '{query}'"

    lines = [f"Notes matching '{query}' ({len(results)} found):"]
    for title, snippet in results[:max_results]:
        lines.append(f"  [{title}] {snippet.strip()}")
    return "\n".join(lines)
```

#### 2.4 Replace send_notification

```python
def send_notification(title: str, message: str) -> str:
    """Send a Windows toast notification."""
    if not _is_windows():
        return f"Notifications are only available on Windows. Would have sent: '{title}'"

    try:
        # Use PowerShell for toast notification
        ps_script = f'''
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $textNodes = $template.GetElementsByTagName("text")
        $textNodes.Item(0).AppendChild($template.CreateTextNode("{title}")) > $null
        $textNodes.Item(1).AppendChild($template.CreateTextNode("{message}")) > $null
        $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier().Show($toast)
        '''
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, timeout=10
        )
        return f"Notification sent: '{title}'"
    except Exception as exc:
        # Fallback: use msg.exe
        try:
            subprocess.run(["msg", "*", f"{title}: {message}"], capture_output=True, timeout=5)
            return f"Notification sent (fallback): '{title}'"
        except Exception:
            return f"Error sending notification: {exc}"
```

#### 2.5 Facade en Registry

Actualizar `core/tools/registry.py:335-405` (`register_macos_tools`) para que registre handlers que ruteen según plataforma.

**Alternativa más limpia:** crear `register_platform_tools()` que registre los handlers correctos según `platform.system()`:

```python
def register_platform_tools(registry: ToolRegistry) -> None:
    """Register platform-specific tools (macOS or Windows)."""
    if platform.system() == "Darwin":
        from integrations.macos_apps import (
            create_note, search_notes, send_notification, spotlight_search
        )
        # ...register macOS handlers...
    elif platform.system() == "Windows":
        from integrations.windows_apps import (
            file_search, create_note, search_notes, send_notification
        )
        # ...register Windows handlers...
    else:
        # Linux: stub handlers
        pass
```

Y en `main.py`, llamar `register_platform_tools()` en vez de `register_macos_tools()`.

**Archivos a modificar:**
- `integrations/windows_apps.py` — **nuevo**
- `core/tools/registry.py` — `register_platform_tools()` o bifurcación condicional
- `main.py` — actualizar registro de tools

---

## Fase 3: Desktop Automation

### Estado Actual

`core/automation/` (4 archivos, ~640 líneas total):
- `recorder.py`: CGEventTap para capturar eventos de teclado/mouse
- `generalizer.py`: LLM generalization → AppleScript
- `workflow_store.py`: SQLite store para workflows AppleScript
- `tools.py`: Tool handlers (start_recording, stop_recording, run_workflow)

### Estrategia

Windows no tiene CGEventTap ni AppleScript. Reemplazar con:

| Componente macOS | Windows Equivalent |
|---|---|
| CGEventTap | `pywinauto` + `keyboard`/`mouse` libraries |
| AppleScript output | PowerShell script + UIA actions |
| osascript execution | PowerShell -Command |

#### 3.1 Windows Recorder

```python
"""Windows automation recorder — captures keyboard/mouse via pywinauto + keyboard library."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class ActionEvent:
    event_type: str  # key_down, key_up, click, move
    key: str = ""
    x: int = 0
    y: int = 0
    timestamp: float = 0.0
    modifiers: list[str] = field(default_factory=list)


class WindowsRecorder:
    """Record keyboard and mouse events on Windows using keyboard/mouse hooks."""

    def __init__(self) -> None:
        self._recording = False
        self._events: list[ActionEvent] = []
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def events(self) -> list[ActionEvent]:
        with self._lock:
            return list(self._events)

    def start(self) -> None:
        if self._recording:
            return
        self._recording = True
        self._events = []
        self._thread = threading.Thread(target=self._hook_loop, daemon=True)
        self._thread.start()
        logger.info("WindowsRecorder started")

    def stop(self) -> list[ActionEvent]:
        self._recording = False
        if self._thread:
            self._thread.join(timeout=2)
        with self._lock:
            events = list(self._events)
        logger.info("WindowsRecorder stopped — {} events", len(events))
        return events

    def _hook_loop(self) -> None:
        """Background thread that captures events via keyboard/mouse libraries."""
        try:
            import keyboard as kb
            import mouse as ms
        except ImportError:
            logger.error("keyboard/mouse libraries not installed")
            self._recording = False
            return

        def on_key(e: kb.KeyboardEvent) -> None:
            if not self._recording:
                return
            with self._lock:
                self._events.append(ActionEvent(
                    event_type="key_down" if e.event_type == "down" else "key_up",
                    key=e.name,
                    timestamp=time.time(),
                ))

        def on_click(e: ms.ButtonEvent) -> None:
            if not self._recording:
                return
            with self._lock:
                self._events.append(ActionEvent(
                    event_type="click",
                    x=e.x or 0,
                    y=e.y or 0,
                    timestamp=time.time(),
                ))

        def on_move(e: ms.MoveEvent) -> None:
            if not self._recording:
                return
            # Throttle mouse moves — record every 10th
            if hasattr(on_move, "_skip"):
                on_move._skip = (on_move._skip + 1) % 10
                if on_move._skip != 0:
                    return
            else:
                on_move._skip = 0
            with self._lock:
                self._events.append(ActionEvent(
                    event_type="move",
                    x=e.x or 0,
                    y=e.y or 0,
                    timestamp=time.time(),
                ))

        kb.hook(on_key)
        ms.hook(click=on_click, move=on_move)

        while self._recording:
            time.sleep(0.1)

        kb.unhook_all()
        ms.unhook_all()
```

#### 3.2 Windows Generalizer

Reemplazar `generalizer.py` para generar PowerShell en vez de AppleScript:

```python
"""Windows automation generalization — events → PowerShell script."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GeneralizationResult:
    name: str
    powershell: str
    description: str
    parameters: dict[str, str] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)


class PowerShellGeneralizerError(Exception):
    pass


async def generalize_events(
    events: list[Any],
    provider: Any,
) -> GeneralizationResult:
    """Use LLM to convert raw events into a PowerShell automation script."""
    # Build event summary for LLM
    summary_lines = []
    for i, e in enumerate(events[:100]):
        if e.event_type == "key_down":
            mods = f" ({'+'.join(e.modifiers)})" if e.modifiers else ""
            summary_lines.append(f"{i}. Press key '{e.key}'{mods}")
        elif e.event_type == "click":
            summary_lines.append(f"{i}. Click at ({e.x}, {e.y})")
        elif e.event_type == "move":
            summary_lines.append(f"{i}. Move to ({e.x}, {e.y})")

    summary = "\n".join(summary_lines)

    system_prompt = """Eres un generador de scripts de automatización para Windows.
Convierte la secuencia de acciones capturadas en un script de PowerShell
que use Add-Type -AssemblyName System.Windows.Forms y SendKeys / mouse_event
para reproducir las acciones.

Reglas:
- Usa [System.Windows.Forms.SendKeys]::SendWait() para teclas
- Usa [System.Windows.Forms.Cursor]::Position para mouse
- Usa user32.dll::mouse_event para clicks
- Incluye sleeps entre acciones (Start-Sleep -Milliseconds X)
- El script debe ser autocontenido y ejecutable con powershell -File

Responde SOLO con JSON:
{"name": "...", "script": "...", "description": "...", "parameters": {...}, "tags": [...]}
"""

    response = await provider.complete(system_prompt, summary)
    # Parse JSON from response...
    # Same logic as existing generalizer.py but with PowerShell prompt
```

#### 3.3 Conditional Import

En `core/automation/__init__.py`:

```python
"""Desktop Automation — cross-platform."""

from __future__ import annotations

import platform

if platform.system() == "Darwin":
    from core.automation.recorder import MacOSRecorder as ActionRecorder  # type: ignore[assignment]
elif platform.system() == "Windows":
    from core.automation.recorder_windows import WindowsRecorder as ActionRecorder  # type: ignore[assignment]
else:
    ActionRecorder = None  # type: ignore[misc]
```

**Archivos a modificar:**
- `core/automation/recorder_windows.py` — **nuevo**
- `core/automation/generalizer_windows.py` — **nuevo** (PowerShell variant)
- `core/automation/__init__.py` — platform fork
- `core/automation/tools.py` — actualizar para soportar ambos outputs
- `pyproject.toml` — agregar dependencias `keyboard`, `mouse`

---

## Fase 4: Filesystem & Trash

### Estado Actual

`core/tools/handlers/filesystem.py:402-419` — `delete_file()` usa `osascript` para mover a la Papelera de macOS.

### Estrategia

Usar `send2trash` (cross-platform):

```python
def delete_file(path: str, authorized_paths: list[str]) -> str:
    """Move a file to the Trash/Recycle Bin (cross-platform)."""
    _require_authorized_path(path, authorized_paths, operation="eliminar")
    p = Path(path).resolve()
    if not p.exists():
        return f"Error: file not found: {path}"
    if not p.is_file():
        return f"Error: not a regular file: {path}"
    try:
        import send2trash
        send2trash.send2trash(str(p))
        logger.info("delete_file: moved {} to Recycle Bin", p)
        return f"File moved to Recycle Bin: {p}"
    except Exception as exc:
        # Fallback: hard delete
        try:
            p.unlink()
            return f"File deleted: {p}"
        except Exception as exc2:
            return f"Error deleting file: {exc2}"
```

**Archivos a modificar:**
- `core/tools/handlers/filesystem.py:402-419` — reemplazar osascript con send2trash
- `pyproject.toml` — agregar `send2trash>=1.8.0`

---

## Fase 5: Shell Scripts → PowerShell

### Estado Actual

| Script | Propósito | Líneas |
|---|---|---|
| `bin/start_engine.sh` | Iniciar llama.cpp server | ~70 |
| `scripts/cerebro_desktop_launcher.sh` | Launcher para desktop | ~205 |
| `scripts/cerebro_desktop_stop.sh` | Stop para desktop | ~25 |
| `ui/tray/src-tauri/resources/cerebro_desktop_launcher.sh` | (copia) | ~205 |
| `ui/tray/src-tauri/resources/cerebro_desktop_stop.sh` | (copia) | ~25 |

### Estrategia

Crear equivalentes `.bat` + `.ps1`. Los scripts .sh existentes quedan para macOS/Linux.

#### 5.1 start_engine.bat

```batch
@echo off
setlocal enabledelayedexpansion

REM Windows llama.cpp engine starter
REM Usage: start_engine.bat chat|embed

set SERVER_BIN=llama-server.exe
set MODEL_DIR=bin\models
set CHAT_ARGS_FILE=config\chat.args

if "%1"=="" (
    echo Usage: %~nx0 chat^|embed
    exit /b 1
)

REM Kill any existing llama-server on the target port
set PORT=8080
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%PORT%') do (
    taskkill /F /PID %%a 2>nul
)
timeout /t 2 /nobreak >nul

REM Read model from chat.args (first line)
set /p MODEL=<%CHAT_ARGS_FILE%
set MODEL_PATH=%MODEL_DIR%\%MODEL%

if not exist "%MODEL_PATH%" (
    echo Model not found: %MODEL_PATH%
    exit /b 1
)

echo Starting llama-server on port %PORT% with model %MODEL%...
start "llama-server" "%SERVER_BIN%" -m "%MODEL_PATH%" --port %PORT% --ctx-size 4096 -ngl 99
echo Engine started. Check logs at ~\.cerebro\logs\
```

#### 5.2 cerebro_desktop_launcher.ps1

```powershell
param(
    [string]$CerebroRoot = $env:CEREBRO_ROOT
)

if (-not $CerebroRoot) {
    $configPath = "$env:USERPROFILE\.cerebro\desktop.json"
    if (Test-Path $configPath) {
        $config = Get-Content $configPath | ConvertFrom-Json
        $CerebroRoot = $config.cerebro_root
    }
}

if (-not $CerebroRoot -or -not (Test-Path $CerebroRoot)) {
    Write-Error "Cerebro root not found"
    exit 1
}

$logDir = "$env:USERPROFILE\.cerebro\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# Kill any existing cerebro process
Get-Process -Name "python" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match "main.py" } |
    Stop-Process -Force

# Start backend
$backendLog = "$logDir\backend.log"
$python = "python"
if (Test-Path "$CerebroRoot\.venv\Scripts\python.exe") {
    $python = "$CerebroRoot\.venv\Scripts\python.exe"
}

Start-Process -NoNewWindow -FilePath $python -ArgumentList "main.py" `
    -WorkingDirectory $CerebroRoot `
    -RedirectStandardOutput $backendLog `
    -RedirectStandardError $backendLog

# Start engine
& "$CerebroRoot\bin\start_engine.bat" chat

Write-Output "Cerebro started. Logs: $logDir"
```

#### 5.3 Rust Launcher Update

`ui/tray/src-tauri/src/launcher.rs:94`:

```rust
// Before (macOS):
let output = Command::new("/bin/bash")
    .arg(&script)
    .output()
    .map_err(|e| format!("Failed to run {}: {e}", script.display()))?;

// After (cross-platform):
let shell = if cfg!(target_os = "windows") { "cmd" } else { "/bin/bash" };
let arg = if cfg!(target_os = "windows") { "/C" } else { "" };
let output = Command::new(shell)
    .arg(arg)
    .arg(&script)
    .output()
```

Y actualizar `resolve_script()` para buscar `.bat`/`.ps1` en Windows:

```rust
fn resolve_script<R: tauri::Runtime, M: Manager<R>>(
    manager: &M,
    script_name: &str,
) -> Result<PathBuf, String> {
    // Try platform-specific extension first
    let script_path = if cfg!(target_os = "windows") {
        let bat = script_name.replace(".sh", ".bat");
        // Also try .ps1
        // ...
    } else {
        script_name.to_string()
    };
    // ...rest of existing logic...
}
```

#### 5.4 lsof → netstat

En `main.py:160` y `ui/tray/server.py:1836`:

```python
def find_process_on_port(port: int) -> list[int]:
    """Cross-platform: find PIDs listening on a port."""
    if platform.system() == "Windows":
        result = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True, text=True, timeout=5
        )
        pids = []
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.strip().split()
                if parts:
                    pids.append(int(parts[-1]))
        return pids
    else:
        result = subprocess.run(
            ["lsof", "-t", "-i", f":{port}", "-sTCP:LISTEN"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return [int(p) for p in result.stdout.strip().split()]
        return []
```

#### 5.5 bash subprocess calls

Reemplazar `subprocess.Popen(["bash", ...])` con `subprocess.Popen` que detecte plataforma:

```python
def _run_script(script_path: str, args: list[str] | None = None) -> subprocess.Popen:
    """Run a shell script cross-platform."""
    if platform.system() == "Windows":
        ext = Path(script_path).suffix
        if ext == ".bat":
            cmd = ["cmd", "/c", script_path]
        else:
            cmd = ["powershell", "-NoProfile", "-File", script_path]
    else:
        cmd = ["bash", script_path]
    if args:
        cmd.extend(args)
    return subprocess.Popen(cmd, ...)
```

**Archivos a modificar:**
- `bin/start_engine.bat` — **nuevo**
- `scripts/cerebro_desktop_launcher.ps1` — **nuevo**
- `scripts/cerebro_desktop_stop.ps1` — **nuevo**
- `ui/tray/src-tauri/resources/` — agregar .bat/.ps1
- `ui/tray/src-tauri/src/launcher.rs` — platform-aware shell
- `ui/tray/src-tauri/tauri.conf.json` — agregar recursos Windows
- `main.py:160-175` — lsof → netstat
- `ui/tray/server.py:1836` — lsof → netstat
- `core/inference/health_monitor.py:40` — bash → Popen platform-aware

---

## Fase 6: Tauri/Rust Adjustments

### 6.1 Cargo.toml — Conditional Dependencies

```toml
[target.'cfg(target_os = "macos")'.dependencies]
cocoa = "0.26"

[target.'cfg(target_os = "windows")'.dependencies]
# Windows-specific crates if needed
```

### 6.2 lib.rs — Conditional Cocoa

El bloque `#[cfg(target_os = "macos")]` en `lib.rs:35-47` ya es condicional. **No requiere cambios.**

### 6.3 tauri.conf.json — Platform-Specific Settings

```json
{
  "bundle": {
    "targets": "all",
    "icon": [
      "icons/32x32.png",
      "icons/128x128.png",
      "icons/128x128@2x.png",
      "icons/icon.icns",
      "icons/icon.ico"
    ],
    "resources": {
      "macos": [
        "icons/tray-icon.png",
        "resources/cerebro_desktop_launcher.sh",
        "resources/cerebro_desktop_stop.sh"
      ],
      "windows": [
        "icons/tray-icon.png",
        "resources/cerebro_desktop_launcher.ps1",
        "resources/cerebro_desktop_stop.ps1",
        "resources/cerebro_desktop_launcher.bat",
        "resources/cerebro_desktop_stop.bat"
      ]
    }
  },
  "app": {
    "windows": [
      {
        "label": "main",
        "title": "Cerebro",
        "width": 960,
        "height": 708,
        "minWidth": 400,
        "minHeight": 500,
        "resizable": true,
        "decorations": true,
        "titleBarStyle": "Overlay"
      }
    ]
  }
}
```

Nota: `titleBarStyle: "Overlay"` es ignorado en Windows (no causa error, solo no se aplica).

### 6.4 Shortcut Key

El hotkey `cmd+shift+space` en `config/settings.toml` y `lib.rs:52`:

```rust
// lib.rs:52
let shortcut = Shortcut::new(
    Some(Modifiers::SUPER | Modifiers::SHIFT),  // macOS: Cmd+Shift
    Code::Space,
);
```

En Windows, `Modifiers::SUPER` es la tecla Windows. Si se quiere Ctrl+Shift+Space:

```rust
let shortcut = if cfg!(target_os = "windows") {
    Shortcut::new(Some(Modifiers::CONTROL | Modifiers::SHIFT), Code::Space)
} else {
    Shortcut::new(Some(Modifiers::SUPER | Modifiers::SHIFT), Code::Space)
};
```

**Archivos a modificar:**
- `ui/tray/src-tauri/tauri.conf.json` — recursos condicionales
- `ui/tray/src-tauri/src/lib.rs` — shortcut platform-aware

---

## Fase 7: Config & Defaults

### 7.1 settings.toml — Windows Defaults

```toml
[files]
# Windows default
cerebro_files_path = "%USERPROFILE%\\Desktop\\CerebroFiles"
authorized_read_paths = ["%USERPROFILE%\\Desktop\\SecondBrain", "%USERPROFILE%\\Desktop\\CerebroFiles"]
authorized_write_paths = ["%USERPROFILE%\\Desktop\\CerebroFiles"]

[ui]
hotkey = "ctrl+shift+space"    # Windows hotkey convention

[calendar]
use_apple_calendar = false     # ya está en false
use_outlook = false             # nuevo: activar en Windows

[mlx]
enabled = "false"               # MLX no disponible en Windows
```

### 7.2 main.py — Defaults por Plataforma

```python
def _default_cerebro_files_path() -> str:
    if platform.system() == "Windows":
        return os.path.join(os.environ["USERPROFILE"], "Desktop", "CerebroFiles")
    return os.path.expanduser("~/Desktop/CerebroFiles")

CEREBRO_FILES_PATH = os.path.expanduser(
    os.getenv("CEREBRO_FILES_PATH", _default_cerebro_files_path())
)
```

### 7.3 lite-8gb.env — Windows Variant

Crear `config/profiles/lite-8gb-windows.env`:

```env
# Lite profile for 8GB Windows machines
CEREBRO_LLAMACPP_SIMPLE=true
CEREBRO_MLX_ENABLED=false
CEREBRO_PROACTIVE_CONTEXT=false
CEREBRO_EMBEDDINGS_BACKEND=local
CEREBRO_WEB_BACKEND=duckduckgo
CEREBRO_CALENDAR_BACKEND=ics
CEREBRO_FILES_PATH=%USERPROFILE%\Desktop\CerebroFiles
```

---

## Fase 8: GPU Detection

### Estado Actual

`core/inference/fleet/hardware_monitor.py` detecta Apple Silicon (`arm64` → Metal) o NVIDIA (`nvidia-smi`).

### Estrategia

Agregar detección de DirectML y CUDA en Windows:

```python
def snapshot() -> HardwareSnapshot:
    # ...existing RAM/CPU logic...

    gpu_backend = "none"
    gpu_vram_total_gb = 0.0
    gpu_vram_available_gb = 0.0
    unified_memory = False

    if platform.processor() in ("arm", "arm64"):
        # Apple Silicon
        gpu_backend = "metal"
        unified_memory = True
        gpu_vram_total_gb = ram_total_gb
        gpu_vram_available_gb = ram_available_gb
    elif platform.system() == "Windows":
        # Try NVIDIA CUDA
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.total,memory.free", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split(",")
                gpu_backend = "cuda"
                gpu_vram_total_gb = float(parts[0]) / 1024
                gpu_vram_available_gb = float(parts[1]) / 1024
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        if gpu_backend == "none":
            # Try DirectML via ONNX Runtime
            try:
                import onnxruntime
                if "DmlExecutionProvider" in onnxruntime.get_available_providers():
                    gpu_backend = "directml"
                    # DirectML shares system RAM
                    gpu_vram_total_gb = ram_total_gb * 0.5  # estimate
                    gpu_vram_available_gb = ram_available_gb * 0.5
            except ImportError:
                pass

        if gpu_backend == "none":
            # Try DirectX via dxdiag
            try:
                result = subprocess.run(
                    ["dxdiag", "/t", "dxdiag.txt"],
                    capture_output=True, timeout=10
                )
                # Parse output for VRAM
                # ...
            except Exception:
                pass
    # ...rest...
```

**Archivos a modificar:**
- `core/inference/fleet/hardware_monitor.py` — agregar detección CUDA/DirectML

---

## Fase 9: Testing

### 9.1 Mock Platform Layer

Crear `tests/conftest_windows.py`:

```python
"""Windows-specific test fixtures."""

import platform
from unittest.mock import patch

import pytest


@pytest.fixture
def mock_windows():
    """Mock platform.system() to return 'Windows'."""
    with (
        patch.object(platform, "system", return_value="Windows"),
        patch("core.inference.platform.is_apple_silicon", return_value=False),
        patch("core.inference.platform.mlx_available", return_value=False),
    ):
        yield
```

### 9.2 Windows-Specific Tests

```python
"""Test Windows-specific backends."""

import pytest


class TestWindowsCalendarBackend:
    async def test_outlook_get_upcoming(self, mock_windows):
        # ...test Outlook COM backend...


class TestWindowsApps:
    def test_file_search_powershell(self, mock_windows):
        # ...test Windows file search...

    def test_create_note_windows(self, mock_windows):
        # ...test Windows notes...

    def test_send_notification_windows(self, mock_windows):
        # ...test Windows toast notification...


class TestWindowsRecorder:
    def test_start_stop(self, mock_windows):
        # ...test Windows recorder...


class TestDeleteFileWindows:
    def test_delete_file_send2trash(self, mock_windows, tmp_path):
        # ...test send2trash...
```

### 9.3 CI/CD — Windows Pipeline

Agregar a `.github/workflows/` (o similar):

```yaml
windows-tests:
  runs-on: windows-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: "3.11"
    - name: Install dependencies
      run: |
        python -m venv .venv
        .venv\Scripts\pip install -e ".[dev,windows]"
    - name: Run tests
      run: |
        .venv\Scripts\pytest tests/ --cov=core --cov-fail-under=70 -x -q
```

---

## Appendix A: Dependency Map

```
┌────────────────────────────────────────────────┐
│               main.py / app_state               │
├────────┬────────┬────────┬────────┬─────────────┤
│ Calendar│ macOS  │ Desktop │ Filesys │  Scripts   │
│ Reader  │ Apps   │ Autom.  │  tem    │  & Rust    │
├────────┼────────┼────────┼────────┼─────────────┤
│  .ics   │Spotlight│CGEvent │osascript│ /bin/bash  │
│  (OK)   │(mdfind) │ (Quartz)│(Finder) │  lsof      │
│         │        │        │  Trash  │            │
│ Apple   │ Apple  │AppleScr│        │  pkill     │
│ Cal.    │ Notes  │ ipt    │        │            │
│ (JXA)   │(JXA)   │ gen    │        │  Homebrew  │
│         │        │        │        │  paths     │
│ Outlook │Notifs  │UIA     │send2-  │  netstat   │
│ (COM)   │(toast) │(Win)   │trash   │  taskkill  │
│         │        │        │        │            │
│ Google  │File    │PowerSh │        │  PowerShell│
│ (API)   │Search  │ell gen │        │  .bat/.ps1 │
│         │(WinIdx)│(Win)   │        │            │
└────────┴────────┴────────┴────────┴─────────────┘
  ▼
  macOS-only (reemplazar)
  ▒  Windows native (nuevo)
  ─  Cross-platform (sin cambios)
```

---

## Appendix B: API Equivalence Table

| macOS API | Windows API | Library |
|---|---|---|
| `CGEventTapCreate` | `SetWindowsHookEx(WH_KEYBOARD_LL)` / `WH_MOUSE_LL` | `keyboard` + `mouse` (Python) |
| `osascript -e "..."` | `powershell -Command "..."` | `subprocess` |
| `mdfind -name query` | `Get-ChildItem -Recurse -Filter *query*` | PowerShell |
| `display notification` | `[Windows.UI.Notifications]::ToastNotification` | PowerShell |
| Apple Notes via JXA | Sticky Notes API / .txt files | `pathlib` |
| Apple Calendar via JXA | Outlook COM / Windows Calendar API | `win32com.client` |
| `lsof -t -i :PORT` | `netstat -ano \| findstr :PORT` | `subprocess` |
| `pkill -f process` | `taskkill /F /IM process.exe` | `subprocess` |
| `nvidia-smi` | `nvidia-smi` (same!) | `subprocess` |
| `osascript ... delete POSIX file` | `send2trash.send2trash()` | `send2trash` |
| `osascript ... tell app "Finder"` | `shell32.SHFileOperationW` (FO_DELETE) | `send2trash` (wraps it) |
| `/bin/bash script.sh` | `cmd /c script.bat` | `subprocess` |

---

## Resumen de Archivos a Crear

| Archivo | Propósito | Dependencias |
|---|---|---|
| `integrations/windows_apps.py` | File search, notes, notifications | pywin32, winsdk |
| `integrations/calendar_backends/outlook.py` | Outlook Calendar COM backend | pywin32 |
| `integrations/calendar_backends/__init__.py` | Abstract base + registry | — |
| `core/automation/recorder_windows.py` | Windows event recorder | keyboard, mouse |
| `core/automation/generalizer_windows.py` | PowerShell workflow generation | — |
| `core/utils/paths.py` | Cross-platform path resolution | — |
| `core/inference/platform_win.py` | Windows GPU detection | onnxruntime (opcional) |
| `bin/start_engine.bat` | Windows llama.cpp launcher | — |
| `scripts/cerebro_desktop_launcher.ps1` | Windows desktop launcher | — |
| `scripts/cerebro_desktop_stop.ps1` | Windows desktop stopper | — |
| `ui/tray/src-tauri/resources/cerebro_desktop_launcher.bat` | Tauri Windows launcher | — |
| `ui/tray/src-tauri/resources/cerebro_desktop_stop.bat` | Tauri Windows stopper | — |
| `config/profiles/lite-8gb-windows.env` | Windows lite profile | — |
| `tests/conftest_windows.py` | Windows test fixtures | pytest |

## Resumen de Archivos a Modificar

| Archivo | Cambio |
|---|---|
| `main.py` | Path defaults, lsof→netstat, bash→platform-aware, platform_tools registration |
| `ui/tray/server.py` | lsof→netstat, path resolution |
| `ui/tray/src-tauri/src/launcher.rs` | Platform-aware shell, .bat/.ps1 resolution |
| `ui/tray/src-tauri/src/lib.rs` | Platform-aware shortcut |
| `ui/tray/src-tauri/tauri.conf.json` | Windows resources, conditional bundle |
| `core/tools/registry.py` | `register_platform_tools()` en vez de `register_macos_tools()` |
| `core/tools/handlers/filesystem.py` | send2trash en vez de osascript |
| `core/automation/__init__.py` | Platform fork (MacOSRecorder vs WindowsRecorder) |
| `core/automation/tools.py` | Soporte PowerShell output |
| `core/inference/fleet/hardware_monitor.py` | CUDA + DirectML detection |
| `integrations/calendar_reader.py` | CalendarReader facade → plugin architecture |
| `config/settings.toml` | Windows defaults (hotkey, paths, MLX off) |
| `pyproject.toml` | `[windows]` extra dependencies |
| `core/tools/handlers/calendar.py` | Import del backend correcto según plataforma |
| `core/agents/context_enricher.py` | Calendar backend detection |

---

**Nota final:** Muchas features ya tienen guards `platform.system() != "Darwin"` que retornan strings de error elegantes. En Windows, estos mismos guards harán que las herramientas macOS retornen mensajes como "Apple Notes is only available on macOS" — funcional, pero no ideal. El port completo reemplaza esos stubs con implementaciones reales de Windows.
