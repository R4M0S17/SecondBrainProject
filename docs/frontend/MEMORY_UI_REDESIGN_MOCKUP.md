# Mockup: Rediseño de la sección Memoria (frontend)

**Problemas detectados:**
- Etiquetas técnicas expuestas al usuario (`working_memory`, `last_consolidation`, `messages_in_short_term`, `recall_rate`)
- "Sesión actual" y "Resumen de sesión" parecen duplicados
- Jerarquía plana — todo en una sola lista sin separar propósito
- La "memoria de trabajo" parece debugging dump
- El usuario no distingue entre "lo que el agente recuerda" vs "el contexto de la conversación actual"

---

## 1. Arquitectura de información (tres pilares)

Cada pilar es una sección claramente diferenciada en la página de Memoria:

```
┌────────────────────────────────────────────────────────┐
│  🧠 MEMORIA                                           │
│  Enséñale a Cerebro lo que te importa                  │
├────────────────────────────────────────────────────────┤
│                                                        │
│  ┌─ PESTAÑAS ──────────────────────────────────────┐  │
│  │  [Hechos guardados]  [Sesión actual]  [Recall]  │  │
│  └─────────────────────────────────────────────────┘  │
│                                                        │
│  ┌─ CONTENIDO DE PESTAÑA ─────────────────────────┐   │
│  │  (cambia según pestaña activa)                  │   │
│  └─────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────┘
```

---

## 2. Pestaña "Hechos guardados" (antes "Saved facts" + stats + lista)

```
┌─ Hechos guardados ────────────────────────────────────┐
│                                                        │
│  [📊 12 hechos]  [📌 3 fijados]  [🎯 85% recall]     │
│                                                        │
│  [+ Añadir hecho]                                      │
│                                                        │
│  [Todos] [Fijados] [Preferencias] [Código] [Académico] │
│                                                        │
│  ┌─────────────────────────────────────────────────┐  │
│  │ 📌 Manual · hace 2h                             │  │
│  │ Prefiero respuestas técnicas en español...      │  │
│  │ [✏️] [📌] [🗑️]  100%                           │  │
│  ├─────────────────────────────────────────────────┤  │
│  │ 🤖 Auto-guardado · hace 1d                      │  │
│  │ El proyecto usa React con TypeScript...         │  │
│  │ [✏️] [📌] [🗑️]  72%                            │  │
│  ├─────────────────────────────────────────────────┤  │
│  │ 📄 Resumido · hace 3d                           │  │
│  │ Las preferencias de usuario incluyen...         │  │
│  │ [✏️] [📌] [🗑️]  45%                            │  │
│  └─────────────────────────────────────────────────┘  │
│                                                        │
└────────────────────────────────────────────────────────┘
```

**Cambios clave:**
- Las 3 cards de stats ahora son icono + número + etiqueta clara
- Los filtros incluyen tags reales del usuario (no solo fijos)
- Botón "Añadir hecho" siempre visible arriba
- Los iconos de source son intuitivos (📌 manual, 🤖 auto, 📄 resumen)

---

## 3. Pestaña "Sesión actual" (antes sidebar lateral)

```
┌─ Sesión actual ───────────────────────────────────────┐
│  Contexto temporal de este chat — solo lectura        │
│                                                        │
│  ┌─ Resumen de conversación ───────────────────────┐  │
│  │                                                  │  │
│  │ El usuario preguntó sobre funciones de Python,   │  │
│  │ flujos de datos, y recibió ejemplos básicos de   │  │
│  │ código. Mostró interés en tutoriales.            │  │
│  │                                                  │  │
│  │ [✏️ Editar resumen] → abre editor inline         │  │
│  └──────────────────────────────────────────────────┘  │
│                                                        │
│  ┌─ Datos de contexto ──────────────────────────────┐  │
│  │                                                   │  │
│  │  📝 8 mensajes en este chat                       │  │
│  │  🔍 Última búsqueda: "python básico"              │  │
│  │  ⏱️ Chat activo desde hace 15 min                 │  │
│  │                                                   │  │
│  └───────────────────────────────────────────────────┘  │
│                                                        │
│  ┌─ Notas automáticas del agente ───────────────────┐  │
│  │  (antes "working_memory" — renombrado)            │  │
│  │                                                   │  │
│  │  • Interés: tutoriales Python → [📌 Guardar]     │  │
│  │  • Archivo mencionado: apuntes.txt → [📌 Guardar]│  │
│  │                                                   │  │
│  └───────────────────────────────────────────────────┘  │
│                                                        │
└────────────────────────────────────────────────────────┘
```

**Cambios clave:**
- "working_memory" → "Notas automáticas del agente"
- Cada nota automática tiene botón "Guardar como hecho" (pasa a Hechos guardados)
- Se eliminaron términos técnicos: `last_consolidation`, `messages_in_short_term`
- Se añadió duración de la sesión y última búsqueda (info útil)
- Resumen editable inline

---

## 4. Pestaña "Recall" (antes abajo de todo)

```
┌─ ¿Qué recuerda Cerebro? ─────────────────────────────┐
│                                                        │
│  Prueba qué hechos guardados coincidirían con una     │
│  pregunta — no se envía nada al chat.                  │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │  🔍 ¿Qué sabe Cerebro sobre...              [Buscar] │
│  └──────────────────────────────────────────────────┘  │
│                                                        │
│  ┌─ Resultados ────────────────────────────────────┐  │
│  │                                                   │  │
│  │  ████████████░░░ 92% · Prefiero respuestas...    │  │
│  │  ██████░░░░░░░░░ 45% · El proyecto usa React...  │  │
│  │                                                   │  │
│  └───────────────────────────────────────────────────┘  │
│                                                        │
└────────────────────────────────────────────────────────┘
```

**Cambios clave:**
- Se convierte en pestaña propia en lugar de sección al fondo
- Cambio de label: "¿Qué recordaría Cerebro?" → "¿Qué recuerda Cerebro?"
- Mantiene el mock notice cuando corresponde

---

## 5. Slide-over panel (header → "Agent Memory")

Misma estructura de pestañas pero más angosto. Solo muestra la pestaña activa, sin decoración extra.

```
┌────────────────────┐
│  Memoria del agente│
├────────────────────┤
│ [Hechos] [Sesión]  │ ← tabs más pequeños
├────────────────────┤
│                    │
│ (contenido igual   │
│  que en la pagina  │
│  completa)         │
│                    │
└────────────────────┘
```

---

## 6. Chat — per-message Memory Panel

Se mantiene igual pero se renombra:

```
┌─────────────────────┐
│  MEMORIA            │
├─────────────────────┤
│ 📌 Prefiero respuestas técnicas en español
│ ████████████░░░ 92% │
│                     │
│ 📌 El proyecto usa React + TypeScript
│ ██████░░░░░░░░░ 45% │
└─────────────────────┘
```

Sin cambios funcionales — solo asegurar que el toggle button diga "Memoria" (ya está).

---

## 7. Dashboard — stats card

```
┌─────────────────────────────┐
│  🧠 Recuerdos               │
│  12 hechos · 8 recuperados  │
│  esta sesión                │
└─────────────────────────────┘
```

Sin cambios mayores.

---

## 8. Resumen de cambios vs estado actual

| Aspecto | Actual | Propuesto |
|---|---|---|
| Estadísticas | 3 cards numéricas (Hechos, Recalls, Activos) | 3 cards con iconos + tooltips explicativos |
| Filtros | 5 fijos (All, Pinned, Session, Academic, Code) | Mismos + tags dinámicos del usuario |
| Sidebar sesión | Columna lateral derecha con datos crudos | Pestaña independiente con labels claros |
| working_memory | "Memoria de trabajo" (término técnico) | "Notas automáticas del agente" |
| last_consolidation | Timestamp técnico | Oculto (irrelevante para el usuario) |
| messages_in_short_term | "X mensajes en corto plazo" | "X mensajes en este chat" |
| Recall test | Sección al fondo de Hechos | Pestaña independiente |
| Resumen sesión | Solo lectura | Solo lectura + botón "Editar resumen" |
| Notas automáticas | Sin acción posible | Botón "Guardar como hecho" por item |

---

## 9. Principios de diseño aplicados

1. **Lenguaje del usuario** — nunca mostrar nombres de variables, campos internos, o términos técnicos
2. **Jerarquía con pestañas** — tres conceptos diferentes no compiten por espacio
3. **Acción visible** — "Añadir hecho" siempre disponible, no oculto tras un toggle
4. **Contexto útil** — mostrar lo que el usuario necesita saber (última búsqueda, duración) no lo que el sistema necesita (consolidación)
5. **Progressive disclosure** — los detalles técnicos existen pero están detrás de un "ⓘ" o colapsable

---

## 10. Implementación (26 Jun 2026)

### Archivos creados
| Archivo | Propósito |
|---|---|
| `ui/tray/src/components/memory/FactsTab.tsx` | Stats con iconos + filtros + lista episodios + formulario añadir |
| `ui/tray/src/components/memory/SessionTab.tsx` | Resumen editable + datos de contexto + notas automáticas con botón "Guardar como hecho" |
| `ui/tray/src/components/memory/RecallTab.tsx` | Wrapper de MemoryRecallSearch como pestaña independiente |

### Archivos modificados
| Archivo | Cambio |
|---|---|
| `ui/tray/src/components/memory/MemoryViewContent.tsx` | Refactor completo: ahora es contenedor de tabs (facts/session/recall) |
| `ui/tray/src/components/memory/MemoryEpisodeCard.tsx` | Añadidos iconos Material Symbols por source (smart_toy/description/archive/bookmark) |
| `ui/tray/src/locales/es.json` | Nuevos labels: tab_facts, tab_session, tab_recall, stat_pinned, session_messages, session_last_search, session_duration, session_save_note, save_to_facts, edit_summary, saved_toast. Renombrados: working_memory→"Notas automáticas", short_term_messages→"mensajes en este chat", recall_test→"¿Qué recuerda Cerebro?" |
| `ui/tray/src/locales/en.json` | Mismos cambios en inglés |

### Eliminado del UI (términos técnicos)
- `Última consolidación` — movido a tooltip interno
- `nunca` → ya no se muestra
- `Memoria de trabajo` → reemplazado por "Notas automáticas del agente" / "Agent auto-notes"
- `X mensajes en corto plazo` → "X mensajes en este chat"

### Funcionalidades preservadas
- CRUD completo de episodios (crear, editar, eliminar, fijar)
- Filtros por categoría (Todos, Fijados, Sesión, Académico, Código)
- Búsqueda semántica (Recall)
- Vista compacta (slide-over panel)
- Modal editor de episodios
- Estados de error (stale_backend, unavailable, offline)
- Banner mock
- i18n completo (es/en)

### Funcionalidades nuevas
- **Pestañas** — navegación entre Hechos guardados / Sesión actual / Recall
- **Editar resumen de sesión** — botón "Editar resumen" → inline textarea → guarda como hecho
- **Guardar nota automática como hecho** — cada item de working_memory tiene botón "Guardar como hecho"
- **Iconos de source** — 🤖 Auto-guardado, 📄 Resumido, 🗄️ Archivado, 📌 Manual
- **Stats con iconos** — las 3 stats cards ahora tienen iconos Material Symbols
- **Contexto de sesión** — muestra duración y última búsqueda si están disponibles

### No cambios
- `MemoryBrowserPanel.tsx` — sin cambios (usa `compact` prop que ya existe)
- `MemoryView.tsx` — sin cambios (wrapper puro)
- `ChatWindow.tsx`, `MessageBubble.tsx`, `MemoryPanel.tsx` — sin cambios
