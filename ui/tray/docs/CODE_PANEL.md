# Code Panel

Panel central para tareas de desarrollo, accesible desde el botón **Code** (`code` icon) en la barra lateral izquierda.

## Tabs

### Terminal
Emulador de terminal basado en **xterm.js** con integración al shell del sistema via Tauri.

- Arranca una shell `bash -i` automáticamente al abrir el panel
- stdin/stdout/stderr en tiempo real con coloreado ANSI
- Ctrl+C para kill del proceso en foreground
- Si el shell falla (entorno no-Tauri o sin permisos), fallback a input/output de comandos individuales

### Output
Historial de ejecuciones de tools del agente (script runner, python, etc).

- Lista en orden inverso (más reciente primero)
- Muestra tool name, argumentos, y resultado
- Se alimenta del metadata de los mensajes del chat, no requiere estado adicional

### Scratch
Editor de texto plano para snippets de código.

- Textarea sin restricciones, font mono
- Copia al portapapeles con un clic
- Contador de líneas
- El contenido persiste solo durante la sesión (volátil)

## Dependencias

- `@xterm/xterm` — terminal emulator
- `@xterm/addon-fit` — auto-resize del terminal al contenedor
- `@tauri-apps/plugin-shell` — spawn de procesos del sistema

## Estructura

```
src/components/code/
  CodePanel.tsx          # Componente principal con las 3 tabs
```

El componente se renderiza en `MainLayout.tsx` cuando `activeTab === "code"`.

## Notas

- El terminal no requiere permisos especiales de Tauri para mostrar, pero sí los necesita para spawnear el shell. La capability `shell:allow-spawn` debe estar configurada en `tauri.conf.json > capabilities`.
- El fallback input funciona en cualquier contexto (incluyendo browser dev mode).
- `Scratch` no tiene persistencia — si se necesita mantener texto entre sesiones, conviene migrar a un store o localStorage.
