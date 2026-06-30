# Plan de compatibilidad Windows — Cerebro2

**Rama:** `feature/windows-compat`  
**Objetivo:** Que el proyecto funcione al 100% en Windows 10/11 (x64 y ARM64) sin romper macOS.  
**Duración estimada:** 3–4 semanas de trabajo enfocado.  
**Estrategia:** Feature-flag approach — todo el código nuevo se escribe de forma que macOS sigue funcionando exactamente igual. Se añade comportamiento Windows, no se reemplaza el macOS.

---

## Principios de diseño cross-platform

> Antes de tocar cualquier archivo, tener estos principios claros evita errores de arquitectura.

1. **Nunca usar `if platform == "Darwin"` como último fallback.** Siempre usar `else` explícito con comportamiento Windows correcto, o lanzar `PlatformNotSupportedError` con mensaje claro.
2. **Un solo codebase, cero archivos duplicados.** No copiar `recorder_mac.py` + `recorder_win.py`. Usar clases abstractas con implementaciones por plataforma.
3. **Detectar en runtime, no en import time.** Los imports condicionales con `try/except` son aceptables para librerías opcionales; la lógica de negocio debe estar en métodos.
4. **Los tests deben correr en ambas plataformas.** Cualquier test que mockee `platform.system()` debe hacerlo con `"Darwin"` Y `"Windows"`.
5. **Windows primero en los paths.** Cuando haya duda sobre un path hardcodeado, buscar primero el equivalente Windows — es el más restrictivo.

---

## Fase 0 — Preparación y entorno de prueba

> **Objetivo:** Tener un entorno Windows donde probar cada cambio antes de marcarlo como listo. Sin esto, el plan es teoría.

### 0.1 — Configurar entorno de prueba Windows

**Opción A (recomendada): VM con Parallels o VMware Fusion**
- Windows 11 ARM64 (para M1 Mac)
- Instalar Python 3.11.x desde python.org (importante: usar el instalador oficial, no Microsoft Store)
- Instalar Node.js 20 LTS
- Instalar Rust toolchain: `winget install Rustlang.Rustup`
- Instalar Visual Studio Build Tools 2022 (requiere Rust en Windows para compilar crates con C bindings)
- Instalar Git for Windows

**Opción B: GitHub Actions CI**
- Añadir workflow `.github/workflows/windows-test.yml` que corre `pytest` en `windows-latest`
- Más lento para iterar pero más barato

**Checklist de verificación:**
```
[ ] python --version  → 3.11.x
[ ] node --version    → 20.x
[ ] cargo --version   → 1.7x+
[ ] git --version     → 2.4x+
[ ] pip install -r requirements.txt  → sin errores
[ ] npm install (en ui/tray)         → sin errores
```

### 0.2 — Identificar dependencias Python problemáticas

Ejecutar en Windows antes de empezar:
```powershell
pip install -r requirements.txt 2>&1 | Select-String "ERROR"
```

Dependencias que **no instalan en Windows** y deben quedar opcionales:
- `mlx`, `mlx-lm`, `mlx-vlm` — Apple Silicon only (ya en grupo `[mlx]` de pyproject.toml, OK)
- `pyobjc-framework-Quartz` — macOS only (ya en `try/except`, OK)
- `pyobjc-framework-ApplicationServices` — macOS only (ya en `try/except`, OK)

> **Nota experta:** El `pyproject.toml` actual ya aísla MLX correctamente. El problema real es que `requirements.txt` (si existe generado de pip freeze) puede incluir estas deps sin los markers de plataforma. Verificar que el archivo de requirements use `; sys_platform == "darwin"` markers o eliminar el archivo generado y usar solo `pyproject.toml`.

### 0.3 — Crear script de setup para Windows

Crear `scripts/setup_windows.ps1`:
```powershell
# Script de instalación inicial para Windows
# Equivalente a `make install` en macOS

$ErrorActionPreference = "Stop"

# Crear virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Instalar dependencias Python
pip install --upgrade pip
pip install -e ".[dev]"

# Instalar dependencias frontend
Set-Location ui/tray
npm install
Set-Location ../..

Write-Host "Setup completado. Ejecuta: .\.venv\Scripts\Activate.ps1 && python main.py"
```

**Verificación:**
```
[ ] scripts/setup_windows.ps1 ejecuta sin errores en VM Windows
[ ] python main.py arranca (aunque crashee en otros bloqueadores, debe pasar el import)
```

---

## Fase 1 — Eliminar los 4 bloqueadores de arranque

> **Objetivo:** Que `python main.py` arranque en Windows sin crashear en el proceso de startup.

### 1.1 — Reemplazar `lsof` con `psutil`

**Archivos afectados:**
- `main.py` (líneas 267, 365, 413, 539)
- `ui/tray/server.py` (líneas 3052, 3065)
- `core/inference/engine_manager.py` (línea 70)

**El problema:**
```python
# Código actual — solo funciona en macOS/Linux
result = subprocess.run(["lsof", "-t", "-i", f":{port}", "-sTCP:LISTEN"], ...)
pids = result.stdout.strip().split()
```

**La solución — función utilitaria cross-platform:**

Crear `core/utils/port_utils.py`:
```python
import psutil

def get_pids_on_port(port: int) -> list[int]:
    """Retorna los PIDs escuchando en el puerto dado. Cross-platform."""
    pids = []
    for conn in psutil.net_connections(kind="tcp"):
        if conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
            if conn.pid:
                pids.append(conn.pid)
    return list(set(pids))

def kill_pids_on_port(port: int) -> int:
    """Mata todos los procesos en el puerto. Retorna cantidad matados."""
    killed = 0
    for pid in get_pids_on_port(port):
        try:
            psutil.Process(pid).terminate()
            killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return killed
```

**Reemplazar en todos los archivos afectados** los bloques con `lsof` por llamadas a `get_pids_on_port()` / `kill_pids_on_port()`.

**Test a escribir** (`tests/test_port_utils.py`):
```python
def test_get_pids_on_port_returns_list():
    """Smoke test — debe retornar lista (vacía o con PIDs) en cualquier plataforma."""
    result = get_pids_on_port(99999)  # puerto libre
    assert isinstance(result, list)
    assert result == []
```

**Verificación:**
```
[ ] grep -r "lsof" core/ main.py ui/tray/server.py  → 0 resultados
[ ] pytest tests/test_port_utils.py  → PASS en macOS
[ ] pytest tests/test_port_utils.py  → PASS en Windows VM
```

---

### 1.2 — Reemplazar `delete_file` vía Finder/osascript

**Archivo afectado:** `core/tools/handlers/filesystem.py` (~línea 412)

**El problema:**
```python
# Solo funciona en macOS
subprocess.run(["osascript", "-e", f'tell application "Finder" to delete POSIX file "{p}"'])
```

**La solución:**

Añadir `send2trash` a las dependencias en `pyproject.toml`:
```toml
dependencies = [
    ...
    "send2trash>=1.8.3",
    ...
]
```

Reemplazar la lógica:
```python
from send2trash import send2trash, TrashPermissionError

def _delete_file_to_trash(path: Path) -> dict:
    try:
        send2trash(str(path))
        return {"success": True, "message": f"Movido a papelera: {path.name}"}
    except TrashPermissionError as e:
        return {"success": False, "error": f"Sin permisos: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

> **Nota experta:** `send2trash` funciona en macOS (mueve al Trash nativo), Windows (Recycle Bin) y Linux (freedesktop trash). Es la librería estándar para esto — la usa el explorador de archivos de VS Code.

**Verificación:**
```
[ ] pip install send2trash  → sin errores en Windows
[ ] test manual: crear archivo temporal → llamar delete_file → aparece en Recycle Bin de Windows
[ ] test manual en macOS: misma operación → aparece en Trash
[ ] pytest tests/test_tool_filesystem.py  → PASS en ambas plataformas
```

---

### 1.3 — Arreglar separador de paths en `CEREBRO_AUTHORIZED_READ_PATHS`

**Archivo afectado:** `main.py` (~línea 207)

**El problema:**
```python
# En Windows, "C:\Users\foo" contiene ":" que rompe el split
return [os.path.expanduser(p.strip()) for p in raw.split(":") if p.strip()]
```

**La solución:**
```python
import os

def _parse_authorized_paths(raw: str) -> list[str]:
    # os.pathsep es ";" en Windows, ":" en Unix
    # Pero para compatibilidad con configs existentes en macOS,
    # detectar plataforma explícitamente
    import platform
    sep = ";" if platform.system() == "Windows" else ":"
    return [os.path.expanduser(p.strip()) for p in raw.split(sep) if p.strip()]
```

> **Nota experta:** Usar `os.pathsep` directamente parece correcto pero crea un problema: configs guardadas en macOS con `:` no se pueden mover a Windows. La solución más robusta a largo plazo es cambiar el formato a JSON array en el env var o usar `;` siempre, pero por ahora la detección de plataforma es la menos disruptiva.

**Verificación:**
```
[ ] En Windows: CEREBRO_AUTHORIZED_READ_PATHS="C:\Users\foo;C:\Users\bar" → parsea 2 paths
[ ] En macOS: CEREBRO_AUTHORIZED_READ_PATHS="/home/foo:/home/bar" → parsea 2 paths (sin regresión)
```

---

### 1.4 — Arreglar `/tmp` hardcodeado en sandbox de ejecución

**Archivo afectado:** `core/tools/handlers/execution.py` (~línea 55)

**El problema:**
```python
sandbox_dir = Path("/tmp/cerebro-sandbox")
```

**La solución:**
```python
import tempfile
from pathlib import Path

# En Windows: C:\Users\foo\AppData\Local\Temp\cerebro-sandbox
# En macOS/Linux: /tmp/cerebro-sandbox
sandbox_dir = Path(tempfile.gettempdir()) / "cerebro-sandbox"
```

Aplicar el mismo patrón en cualquier otro lugar donde aparezca `/tmp/` hardcodeado:
```bash
grep -rn '"/tmp/' core/ main.py ui/tray/server.py
```

**Verificación:**
```
[ ] grep -rn '"/tmp/' core/ main.py  → 0 resultados (solo en comentarios/strings de test está OK)
[ ] En Windows: sandbox_dir apunta a TEMP de Windows
[ ] En macOS: sin cambio de comportamiento
```

---

### Checkpoint Fase 1

Antes de continuar a Fase 2, verificar:
```
[ ] python main.py arranca en Windows sin crash en startup
[ ] python main.py arranca en macOS sin regresión
[ ] make test (macOS) → todos los tests pasan
[ ] pip install en Windows → sin errores
```

---

## Fase 2 — Launcher Tauri cross-platform

> **Objetivo:** El frontend Tauri puede arrancar/detener el backend Python y el motor llama.cpp en Windows.

> **Nota experta:** Esta es la fase más compleja técnicamente porque requiere cambios en Rust. La arquitectura actual del launcher asume Unix completamente. La estrategia es mantener el código macOS intacto y añadir una rama Windows que usa `python.exe` directamente.

### 2.1 — Entender la arquitectura actual del launcher

Leer completamente `ui/tray/src-tauri/src/launcher.rs` antes de tocar nada. El launcher hace:
1. Busca el Python del venv en `../.venv/bin/python`
2. Arranca `python main.py` pasando env vars
3. Arranca el motor via `start_engine.sh` con `/bin/bash`
4. Monitorea procesos hijos con handles
5. Los detiene en shutdown

### 2.2 — Crear abstracción de paths por plataforma en Rust

En `launcher.rs`, añadir al inicio:
```rust
#[cfg(target_os = "windows")]
fn venv_python() -> PathBuf {
    PathBuf::from(".venv").join("Scripts").join("python.exe")
}

#[cfg(not(target_os = "windows"))]
fn venv_python() -> PathBuf {
    PathBuf::from(".venv").join("bin").join("python")
}

#[cfg(target_os = "windows")]
fn home_dir() -> PathBuf {
    std::env::var("USERPROFILE")
        .map(PathBuf::from)
        .unwrap_or_else(|_| std::env::var("HOMEDRIVE")
            .and_then(|drive| std::env::var("HOMEPATH").map(|path| PathBuf::from(drive + &path)))
            .unwrap_or_else(|_| PathBuf::from("C:\\Users\\default")))
}

#[cfg(not(target_os = "windows"))]
fn home_dir() -> PathBuf {
    std::env::var_os("HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("/"))
}
```

> **Nota experta:** Mejor aún — añadir el crate `dirs = "5"` al `Cargo.toml` de `src-tauri` y usar `dirs::home_dir()`. Evita mantener esa lógica manualmente. `dirs` es una dependencia de producción ampliamente usada en el ecosistema Tauri.

### 2.3 — Reemplazar el arranque del engine via shell script

**El problema actual:**
```rust
// launcher.rs — BLOQUEADOR en Windows
Command::new("/bin/bash").arg(&script_path)
```

**La solución:** El engine es el binario `llama-server`. En lugar de llamarlo via script shell, llamarlo directamente desde Rust:

```rust
#[cfg(target_os = "windows")]
fn engine_binary_path(resource_dir: &Path) -> PathBuf {
    resource_dir.join("llama-server.exe")
}

#[cfg(not(target_os = "windows"))]
fn engine_binary_path(resource_dir: &Path) -> PathBuf {
    // Intentar Homebrew primero, luego bundled
    let homebrew = PathBuf::from("/opt/homebrew/bin/llama-server");
    if homebrew.exists() {
        return homebrew;
    }
    resource_dir.join("llama-server")
}

fn start_engine(resource_dir: &Path, port: u16) -> Result<Child, Error> {
    let binary = engine_binary_path(resource_dir);
    Command::new(&binary)
        .arg("--port").arg(port.to_string())
        .arg("--model").arg(model_path())
        .spawn()
        .map_err(|e| Error::EngineLaunchFailed(e.to_string()))
}
```

### 2.4 — Bundling del binario llama-server para Windows

En `ui/tray/src-tauri/tauri.conf.json`, la sección `bundle.resources` necesita incluir el binario Windows:

```json
{
  "bundle": {
    "resources": {
      "../../bin/models": "models",
      "../../scripts/cerebro_desktop_common.sh": ".",
      "../../scripts/start_backend.sh": ".",
      "../../scripts/stop_backend.sh": ".",
      "../../scripts/start_engine.sh": ".",
      "../../scripts/stop_engine.sh": "."
    }
  }
}
```

Para Windows, crear `tauri.windows.conf.json` que override resources:
```json
{
  "bundle": {
    "resources": {
      "../../bin/models": "models",
      "../../bin/llama-server.exe": ".",
      "../../scripts/start_backend.ps1": ".",
      "../../scripts/stop_backend.ps1": ".",
      "../../scripts/start_engine.ps1": ".",
      "../../scripts/stop_engine.ps1": "."
    }
  }
}
```

> **Nota experta sobre el binario llama-server en Windows:** Tienes dos opciones:
> 1. **Compilar localmente:** `cmake` + Visual Studio Build Tools. Complejo para el usuario final.
> 2. **Descargar pre-built:** Los releases oficiales de llama.cpp en GitHub incluyen binarios Windows. Crear un script `scripts/download_engine.ps1` que descargue la versión correcta. Este es el approach de Ollama y LM Studio — es la mejor UX para usuarios finales.
>
> Recomiendo opción 2 para esta implementación.

### 2.5 — Scripts PowerShell equivalentes

Crear los scripts PowerShell que el launcher necesita. Estos van en `scripts/`:

**`scripts/start_backend.ps1`:**
```powershell
param([string]$Port = "7842")
$env:CEREBRO_PORT = $Port
$VenvPython = Join-Path $PSScriptRoot ".." ".venv" "Scripts" "python.exe"
$MainPy = Join-Path $PSScriptRoot ".." "main.py"
& $VenvPython $MainPy
```

**`scripts/download_engine.ps1`** (para primer setup):
```powershell
# Descarga llama-server.exe de los releases oficiales de llama.cpp
$Version = "b4567"  # Fijar versión para reproducibilidad
$Url = "https://github.com/ggml-org/llama.cpp/releases/download/$Version/llama-$Version-bin-win-avx2-x64.zip"
$OutPath = Join-Path $PSScriptRoot ".." "bin" "llama-server.exe"
# ... lógica de descarga
```

**Verificación Fase 2:**
```
[ ] cargo build (en Windows)  → sin errores de compilación
[ ] La app Tauri arranca en Windows
[ ] El backend Python arranca via launcher
[ ] El motor llama-server arranca en Windows (si binario disponible)
[ ] En macOS: cero regresión — todo sigue funcionando igual
```

---

## Fase 3 — UI Tauri cross-platform

> **Objetivo:** La interfaz se ve y funciona correctamente en Windows 10/11.

### 3.1 — Window chrome (titlebar)

**Archivo afectado:** `ui/tray/src-tauri/tauri.conf.json`

**El problema:** `"titleBarStyle": "Overlay"` es macOS-only. En Windows produce una ventana sin botones de cerrar/minimizar.

**La solución:** Usar `tauri.windows.conf.json` como override:
```json
{
  "app": {
    "windows": [{
      "titleBarStyle": "default",
      "decorations": true
    }]
  }
}
```

Y en el build de Windows pasar `--config tauri.windows.conf.json`.

Adicionalmente, en React el componente que renderiza el titlebar custom (`ui/tray/src/layouts/Header.tsx`) debe detectar si está en Windows y ocultar los controles macOS:
```typescript
import { platform } from '@tauri-apps/plugin-os';

const isMac = await platform() === 'macos';
// Render traffic-lights solo en macOS
```

### 3.2 — System tray en Windows

El tray icon funciona diferente en Windows:
- macOS: `icon_as_template(true)` → el OS adapta el ícono a dark/light mode
- Windows: necesita icono `.ico` (no `.png`) para mejor calidad

**Acciones:**
1. Crear `icons/tray-icon.ico` (puede ser conversión del `.png` existente)
2. En `lib.rs`, condicionar el template:
```rust
#[cfg(not(target_os = "macos"))]
let tray_icon = TrayIconBuilder::new()
    .icon(app.default_window_icon().unwrap().clone());
    // sin icon_as_template en Windows

#[cfg(target_os = "macos")]
let tray_icon = TrayIconBuilder::new()
    .icon(app.default_window_icon().unwrap().clone())
    .icon_as_template(true);
```

### 3.3 — Evento `Reopen` (dock de macOS)

**Archivo afectado:** `ui/tray/src-tauri/src/lib.rs` (~línea 200)

El código actual maneja `RunEvent::Reopen` (click en el dock de macOS). En Windows el equivalente es hacer clic en la taskbar o en el tray icon.

```rust
tauri::RunEvent::Reopen { has_visible_windows, .. } => {
    // Este evento solo existe en macOS — en Windows esto nunca se llama
    // El tray icon click ya maneja el re-show en Windows via el menu handler
    if !has_visible_windows {
        show_main_window(&app_handle);
    }
}
```

El código actual compila en Windows sin error (el evento nunca dispara), pero verificar que el tray icon click ya hace `show()` en Windows — si no, añadirlo en el handler del tray.

### 3.4 — `visibleOnAllWorkspaces`

**Archivo afectado:** `tauri.conf.json`

Simplemente ignorado en Windows (Tauri lo omite silenciosamente). No requiere cambio, pero documenta este comportamiento en el código para que nadie lo remueva pensando que es un bug.

**Verificación Fase 3:**
```
[ ] La ventana principal tiene botones de cerrar/minimizar/maximizar en Windows
[ ] El tray icon aparece en la bandeja del sistema de Windows
[ ] Click en tray icon → abre la ventana (si estaba oculta)
[ ] En macOS: sin regresión en titlebar, tray, dock behavior
[ ] La app se ve razonablemente bien en Windows (no requiere pixel-perfect, solo funcional)
```

---

## Fase 4 — Features degradados con fallbacks Windows

> **Objetivo:** Cada feature que es macOS-only tiene un comportamiento en Windows: ya sea un equivalente funcional o un mensaje de error claro. Nada crashea silenciosamente.

### 4.1 — Notificaciones del sistema

**Archivo afectado:** `integrations/macos_apps.py`

**El problema:** `send_notification` usa `display notification` de AppleScript. En Windows: silencio total.

**La solución — añadir `plyer`:**
```toml
# pyproject.toml
dependencies = [
    "plyer>=2.1.0",
    ...
]
```

```python
# integrations/notifications.py — nuevo archivo
import platform

def send_system_notification(title: str, message: str, app_name: str = "Cerebro") -> bool:
    """
    Envía notificación nativa. Retorna True si exitoso.
    macOS: notification center vía osascript
    Windows: Windows Toast Notification vía plyer
    Linux: libnotify vía plyer
    """
    system = platform.system()

    if system == "Darwin":
        import subprocess
        script = f'display notification "{message}" with title "{title}" subtitle "{app_name}"'
        result = subprocess.run(["osascript", "-e", script], capture_output=True)
        return result.returncode == 0

    else:
        try:
            from plyer import notification
            notification.notify(
                title=title,
                message=message,
                app_name=app_name,
                timeout=5,
            )
            return True
        except Exception:
            return False
```

Reemplazar la llamada en el tool handler por `send_system_notification()`.

**Verificación:**
```
[ ] En Windows: "send_notification" en el chat → aparece toast en esquina inferior derecha
[ ] En macOS: sin regresión — misma notificación de siempre
[ ] plyer instala sin errores en Windows
```

---

### 4.2 — Búsqueda de archivos (reemplazar `mdfind`)

**Archivo afectado:** `integrations/macos_apps.py` → función `spotlight_search`

**El problema:** `mdfind` es Spotlight de macOS. El tool ya tiene guard de plataforma pero en Windows retorna mensaje de error sin ofrecer alternativa.

**La solución — fallback con `os.walk` + índice simple:**

```python
import os
import fnmatch
from pathlib import Path

def spotlight_search(query: str, scope: str | None = None) -> list[dict]:
    """
    Busca archivos por nombre/contenido.
    macOS: usa mdfind (Spotlight) para búsqueda full-text instantánea
    Windows/Linux: usa os.walk con glob matching (más lento, solo por nombre)
    """
    import platform

    if platform.system() == "Darwin":
        return _spotlight_search_mac(query, scope)
    else:
        return _file_search_fallback(query, scope)

def _file_search_fallback(query: str, scope: str | None = None) -> list[dict]:
    """Búsqueda por nombre de archivo vía os.walk. Limitada a ~50k archivos."""
    search_root = Path(scope) if scope else Path.home()
    # Limitar el scope para no hacer la búsqueda infinitamente lenta
    SEARCH_DIRS = [
        search_root / "Desktop",
        search_root / "Documents",
        search_root / "Downloads",
    ]

    results = []
    query_lower = query.lower()

    for search_dir in SEARCH_DIRS:
        if not search_dir.exists():
            continue
        for root, dirs, files in os.walk(search_dir):
            # Saltar directorios ocultos y node_modules
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules']
            for filename in files:
                if query_lower in filename.lower():
                    full_path = Path(root) / filename
                    results.append({
                        "path": str(full_path),
                        "name": filename,
                        "size": full_path.stat().st_size,
                    })
                    if len(results) >= 20:  # límite razonable
                        return results
    return results
```

> **Nota experta:** Para una búsqueda de archivos Windows realmente buena, integrar con `Everything` de voidtools via su SDK o CLI. Es gratuito, instantáneo, y tiene API HTTP. Pero el fallback con `os.walk` es suficiente para v1 de compatibilidad Windows.

**Verificación:**
```
[ ] En Windows: "busca el archivo presupuesto" → encuentra archivos con ese nombre en Desktop/Documents
[ ] En macOS: sin regresión — sigue usando mdfind
[ ] No cuelga con directorios muy grandes (respetar límite de 20 resultados)
```

---

### 4.3 — Apple Notes → marcar como no disponible en Windows

**Archivo afectado:** `integrations/macos_apps.py` → `create_note`, `search_notes`

Los guards ya existen. Solo verificar que el mensaje de error es claro y que el tool no aparece en la lista de tools disponibles en Windows.

En `core/tools/registry.py`, donde se registra el tool, añadir:
```python
import platform

if platform.system() == "Darwin":
    registry.register(ToolDefinition(
        name="create_note",
        description="Crea una nota en Apple Notes",
        ...
    ))
    # No registrar en Windows — el tool no existirá en la lista
```

**Verificación:**
```
[ ] GET /api/tools en Windows → "create_note" no aparece en la lista
[ ] GET /api/tools en macOS → "create_note" sigue apareciendo
```

---

### 4.4 — Calendar write → desactivado en Windows con mensaje claro

**Archivos afectados:** `core/tools/handlers/calendar.py`, `core/tools/registry.py`

La escritura de calendario (`create_apple_calendar_event`, `delete_apple_calendar_event_by_title`) usa JXA/osascript. En Windows no tiene equivalente razonable sin integrar con Microsoft Graph API (que requiere OAuth y registro de app — out of scope para v1).

**La solución para v1:**
```python
# En calendar.py handlers de escritura
import platform

async def create_apple_calendar_event(params: dict) -> dict:
    if platform.system() != "Darwin":
        return {
            "success": False,
            "error": "Creación de eventos de calendario no disponible en Windows. "
                     "Usa la app Calendar directamente.",
            "platform": platform.system()
        }
    # ... código macOS existente sin cambios
```

Registrar el tool normalmente pero el handler retorna error amigable en no-macOS.

> **Nota experta para v2:** Si se quiere calendar write en Windows, la ruta es Microsoft Graph API + OAuth2. Requiere registrar la app en Azure AD, es un sprint completo de trabajo. Anotar en el roadmap como `windows-calendar-write-v2`.

**Verificación:**
```
[ ] En Windows: "crea evento mañana a las 3pm" → respuesta clara "no disponible en Windows"
[ ] En macOS: sin regresión
```

---

### 4.5 — Automatización de escritorio (CGEventTap) — stub Windows con pynput

**Archivos afectados:** `core/automation/recorder.py`, `core/automation/service.py`

Esta es la feature más compleja. El guard `HAS_QUARTZ` ya previene crashes, pero en Windows el feature está completamente ausente.

**Para Fase 4 (v1): Implementar recording básico con pynput**

`pynput` funciona en Windows, macOS y Linux para capturar eventos de teclado y mouse.

Añadir dependencia:
```toml
# pyproject.toml
dependencies = [
    "pynput>=1.7.7",
    ...
]
```

Crear `core/automation/recorder_windows.py`:
```python
"""
Grabador de acciones para Windows usando pynput.
Captura: clics de mouse (con coordenadas), teclas pulsadas, scroll.
La ejecución de workflows en Windows usa pyautogui (no AppleScript).
"""
from pynput import mouse, keyboard
from dataclasses import dataclass, field
from typing import Any
import threading
import time

@dataclass
class WindowsEventRecorder:
    events: list[dict] = field(default_factory=list)
    _recording: bool = False
    _mouse_listener: Any = None
    _keyboard_listener: Any = None

    def start(self):
        self._recording = True
        self._mouse_listener = mouse.Listener(
            on_click=self._on_click,
            on_scroll=self._on_scroll,
        )
        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
        )
        self._mouse_listener.start()
        self._keyboard_listener.start()

    def stop(self) -> list[dict]:
        self._recording = False
        if self._mouse_listener:
            self._mouse_listener.stop()
        if self._keyboard_listener:
            self._keyboard_listener.stop()
        return self.events.copy()

    def _on_click(self, x, y, button, pressed):
        if pressed and self._recording:
            self.events.append({
                "type": "click",
                "x": x, "y": y,
                "button": str(button),
                "timestamp": time.time(),
            })

    def _on_scroll(self, x, y, dx, dy):
        if self._recording:
            self.events.append({
                "type": "scroll",
                "x": x, "y": y,
                "dx": dx, "dy": dy,
                "timestamp": time.time(),
            })

    def _on_key_press(self, key):
        if self._recording:
            self.events.append({
                "type": "keypress",
                "key": str(key),
                "timestamp": time.time(),
            })
```

Modificar `recorder.py` para ser un dispatcher:
```python
import platform

def get_recorder():
    """Factory: retorna el recorder correcto para la plataforma."""
    if platform.system() == "Darwin" and HAS_QUARTZ:
        return MacOSEventRecorder()  # clase existente
    elif platform.system() == "Windows":
        from core.automation.recorder_windows import WindowsEventRecorder
        return WindowsEventRecorder()
    else:
        raise RecordingUnavailableError(
            f"Grabación no disponible en {platform.system()}"
        )
```

**Para ejecución de workflows en Windows:**

En lugar de AppleScript, los workflows grabados en Windows se ejecutan con `pyautogui`:
```toml
dependencies = [
    "pyautogui>=0.9.54",  # Windows: instala automáticamente pywin32
    ...
]
```

> **Nota experta:** `pyautogui` en Windows requiere que el usuario tenga Python con acceso a `win32api`. En Windows, la automatización también puede usar `pywinauto` (más robusto, entiende la jerarquía de ventanas) o `UIAutomation` (API nativa de Windows). Para v1, `pyautogui` es el camino más rápido. Para v2, `pywinauto` da mejor generalización de workflows porque puede identificar controles por nombre, no solo por coordenadas.

**Verificación:**
```
[ ] En Windows: instalar pynput + pyautogui sin errores
[ ] En Windows: start_recording → mover mouse → stop_recording → retorna lista de eventos
[ ] En macOS: sin regresión — sigue usando CGEventTap
[ ] El LLM puede generalizar los eventos capturados en Windows a un workflow reutilizable
```

---

## Fase 5 — Build pipeline y distribución Windows

> **Objetivo:** Generar un instalador `.msi` o `.exe` para Windows que incluya todo lo necesario.

### 5.1 — Configurar Tauri para build Windows

**Archivo:** `ui/tray/src-tauri/tauri.conf.json`

Añadir configuración de bundle para Windows:
```json
{
  "bundle": {
    "windows": {
      "certificateThumbprint": null,
      "digestAlgorithm": "sha256",
      "timestampUrl": "",
      "wix": {
        "language": "en-US"
      },
      "nsis": {
        "languages": ["English", "Spanish"],
        "displayLanguageSelector": true
      }
    }
  }
}
```

> **Nota experta:** Tauri soporta dos instaladores Windows: **WiX** (MSI clásico) y **NSIS** (exe moderno). Recomiendo NSIS para este proyecto — genera un `.exe` de instalación que users de Windows esperan, y soporta instalación sin elevación de privilegios (modo usuario). WiX requiere más configuración y siempre pide UAC.

### 5.2 — GitHub Actions para build Windows

Crear `.github/workflows/build-windows.yml`:
```yaml
name: Build Windows

on:
  push:
    branches: [feature/windows-compat]
  pull_request:
    branches: [main]

jobs:
  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Setup Node.js 20
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install Rust
        uses: dtolnay/rust-toolchain@stable

      - name: Install Python deps
        run: pip install -e ".[dev]"

      - name: Run Python tests
        run: pytest tests/ -x -q

      - name: Install frontend deps
        working-directory: ui/tray
        run: npm install

      - name: Build Tauri app
        working-directory: ui/tray
        run: npm run tauri build -- --config src-tauri/tauri.windows.conf.json
        env:
          TAURI_SIGNING_PRIVATE_KEY: ""

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: cerebro-windows-installer
          path: ui/tray/src-tauri/target/release/bundle/nsis/*.exe
```

### 5.3 — Crear `build/build_windows.ps1`

El Makefile referencia este archivo pero no existe. Crearlo:
```powershell
# build/build_windows.ps1
# Equivalente a `make build` para Windows
param(
    [string]$Version = "0.2.0",
    [switch]$Sign = $false
)

$ErrorActionPreference = "Stop"

Write-Host "Building Cerebro2 v$Version for Windows..."

# 1. Verificar dependencias
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3.11 requerido. Instalar desde python.org"
}
if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    throw "Rust requerido. Instalar desde rustup.rs"
}

# 2. Instalar deps Python
Write-Host "Instalando dependencias Python..."
pip install -e ".[dev]" --quiet

# 3. Run tests
Write-Host "Ejecutando tests..."
pytest tests/ -x -q
if ($LASTEXITCODE -ne 0) { throw "Tests fallaron" }

# 4. Build frontend + Tauri
Write-Host "Compilando app..."
Set-Location ui/tray
npm install --silent
npm run tauri build -- --config src-tauri/tauri.windows.conf.json
Set-Location ../..

Write-Host "Build completado: ui/tray/src-tauri/target/release/bundle/nsis/"
```

**Verificación Fase 5:**
```
[ ] GitHub Actions build completa sin errores en windows-latest
[ ] El instalador .exe generado instala la app en Windows 11
[ ] La app instalada arranca y muestra la interfaz
[ ] Desinstalación limpia desde "Agregar o quitar programas"
```

---

## Fase 6 — Tests cross-platform y hardening

> **Objetivo:** Que el suite de tests corra en Windows y que los tests reflejen comportamiento real de ambas plataformas.

### 6.1 — Auditar tests existentes para platform-mocking

Buscar todos los mocks de plataforma:
```bash
grep -rn 'platform.system\|sys.platform\|"Darwin"\|"Windows"' tests/
```

Para cada mock encontrado, verificar que hay un test equivalente con `"Windows"`:
```python
# Patrón actual (incompleto)
@pytest.mark.parametrize("platform_name", ["Darwin"])
def test_calendar_backend_selection(platform_name, monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: platform_name)
    ...

# Patrón correcto (completo)
@pytest.mark.parametrize("platform_name,expected_backend", [
    ("Darwin", "apple_calendar"),
    ("Windows", "ics"),
    ("Linux", "ics"),
])
def test_calendar_backend_selection(platform_name, expected_backend, monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: platform_name)
    backend = CalendarManager().get_backend()
    assert backend.name == expected_backend
```

### 6.2 — Añadir GitHub Actions para tests en Windows

Crear `.github/workflows/test-windows.yml`:
```yaml
name: Tests Windows

on: [push, pull_request]

jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -e ".[dev]"
      - run: pytest tests/ -x -q --tb=short
        env:
          CEREBRO_INFERENCE_BACKEND: claude
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

### 6.3 — Smoke test manual en Windows

Checklist de smoke test a correr manualmente en la VM antes de merge a main:

```
SMOKE TEST WINDOWS — Cerebro2 v0.2

Setup:
[ ] Instalador .exe instala sin errores
[ ] App arranca desde el menú Inicio
[ ] El ícono aparece en la bandeja del sistema (system tray)
[ ] Al hacer clic en el tray icon, se abre la ventana

Backend:
[ ] La ventana muestra status "Conectado" o equivalente
[ ] Pregunta simple ("Hola, ¿cómo estás?") → respuesta coherente
[ ] Pregunta de fecha/hora → respuesta correcta (fast path)

Features con fallback:
[ ] "Crea un evento en mi calendario para mañana" → mensaje de "no disponible en Windows"
[ ] "Busca el archivo presupuesto" → lista de archivos (fallback os.walk)
[ ] "Envíame una notificación" → aparece toast de Windows

Features que deben funcionar igual que macOS:
[ ] Indexar una carpeta → barra de progreso → documentos indexados
[ ] Preguntar sobre el contenido de un documento indexado → respuesta con RAG
[ ] Conversación con memoria → la sesión persiste entre mensajes

No regresión macOS:
[ ] Todos los tests pasan en macOS después del merge
[ ] Smoke test macOS básico (chat, calendar, notifications, spotlight) → OK
```

---

## Orden de implementación recomendado

```
Semana 1:
  Fase 0 — Setup entorno Windows (VM o CI)
  Fase 1 — Los 4 bloqueadores de arranque (todo Python, sin Rust)
  → Checkpoint: python main.py arranca en Windows

Semana 2:
  Fase 2 — Launcher Tauri (Rust)
  Fase 3 — UI Tauri cross-platform
  → Checkpoint: la app Tauri corre en Windows

Semana 3:
  Fase 4.1–4.4 — Notificaciones, búsqueda, calendar, notes
  Fase 6.1–6.2 — Tests cross-platform
  → Checkpoint: todos los tests pasan en Windows CI

Semana 4:
  Fase 4.5 — Desktop automation Windows (pynput + pyautogui)
  Fase 5 — Build pipeline + instalador
  → Checkpoint: instalador .exe funcional, smoke test completo
```

---

## Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Binario llama-server Windows inestable | Media | Alto | Usar release oficial de llama.cpp; tener fallback a Claude API |
| Antivirus Windows bloquea la app | Alta | Medio | Firmar el binario con certificado EV Code Signing (~$400/año) o aceptar el warning en v1 |
| CGEventTap vs pynput: pérdida de precisión en recording | Baja | Bajo | pynput tiene misma precisión; el LLM generaliza igual |
| Rust compilation falla en Windows por deps C | Media | Alto | Tener CI con `windows-latest` desde día 1 para detectar temprano |
| Tests de calendario rompen en Windows | Alta | Bajo | Ya hay mocks de plataforma en los tests; solo añadir el caso Windows |

---

## Notas finales del experto

**Lo que NO hacer:**
- No crear dos codebases separados (uno macOS, uno Windows). Es insostenible.
- No usar Electron como alternativa a Tauri en Windows. Tauri funciona bien en Windows — solo falta configuración.
- No postponer los tests de Windows para "al final". El CI de Windows debe correr desde la Fase 1.

**Lo que SÍ priorizar:**
- El launcher (Fase 2) es el cuello de botella técnico más difícil. Empezar a investigarlo en paralelo con la Fase 1.
- `psutil` para reemplazar `lsof` es el cambio más seguro y más impactante. Hacer esto primero.
- Mantener macOS como plataforma de desarrollo principal. Cada cambio debe ser "añadir Windows" no "cambiar para Windows".

**Decisión arquitectural importante:** Dado que el proyecto ya tiene `CEREBRO_INFERENCE_BACKEND=claude`, los tests en CI de Windows pueden correr con el backend Claude API en lugar de necesitar llama.cpp. Esto simplifica enormemente el CI — no hay que lidiar con el binario llama-server en los tests automatizados, solo en el smoke test manual.
