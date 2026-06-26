# Cerebro — Cómo arrancar

Versión en inglés: [`howToRun.md`](howToRun.md).

> **Resumen:** `npm run tauri:dev` → backend automático, **LLM apagado** hasta pulsar **Encender motor** en la barra.

---

## Primera vez (una sola vez)

```bash
cd /Users/mb/Desktop/Javier/SecondBrain
make install
make desktop-config
```

---

## Recomendado — Desarrollo con Tauri (hot-reload, LLM bajo demanda)

### Una terminal

```bash
cd /Users/mb/Desktop/Javier/SecondBrain/ui/tray
npm run tauri:dev
```

| Qué pasa | Detalle |
|----------|---------|
| Ventana Tauri | UI nativa con recarga al guardar |
| Backend `:7842` | Se levanta solo si no está corriendo |
| Motor `:8080` | **No** arranca — usa **Encender motor** / **Apagar motor** |
| Sin motor | Settings, documentos, historial y fast paths (math, calendario lectura…) |

### Dos terminales (opcional, para ver logs del backend)

```bash
# Terminal 1
cd /Users/mb/Desktop/Javier/SecondBrain
make lite          # Mac 8 GB — recomendado

# Terminal 2
cd ui/tray && npm run tauri:dev
```

---

## App instalada (Dock / Aplicaciones)

```bash
make desktop-app && make desktop-install
open /Applications/Cerebro.app
```

Los cambios de código **no** se aplican solos: vuelve a `make desktop-app && make desktop-install`.

---

## Otros modos

| Modo | Comando |
|------|---------|
| Todo junto (legacy, motor auto) | `make dev-full` |
| Solo backend | `make lite` o `make run` |
| Solo motor (terminal) | `make engine` |
| UI en navegador (sin Tauri) | `cd ui/tray && npm run dev` |
| Parar motor | `make desktop-stop-engine` |
| Parar todo | `make desktop-stop` |

---

## El LLM se enciende solo tras unos segundos

El monitor de salud solo reinicia el motor si `~/.cerebro/state/engine.json` tiene `"desired": "on"`. Por defecto es **`off`**.

Si sigue pasando:

```bash
make desktop-stop-engine
rm -f ~/.cerebro/state/engine.json
make desktop-stop-backend   # o cierra la terminal de make lite
cd ui/tray && npm run tauri:dev
```

No uses `make dev-full` si quieres controlar el motor solo con el botón.

---

## Comprobar estado

```bash
curl -s http://127.0.0.1:7842/api/status | jq .engine_ok
```

`false` = backend OK, motor apagado (normal). `true` = listo para chat LLM.

---

## Más documentación

- [`howToRun.md`](howToRun.md) — guía completa en inglés
- [`DESKTOP_ONE_CLICK_LAUNCH.md`](DESKTOP_ONE_CLICK_LAUNCH.md) — empaquetar `.app`
