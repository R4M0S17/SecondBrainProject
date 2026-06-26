# Plan: Rediseño de la pestaña Sesión + Historial de conversaciones [✔ DONE]

**Estado:** ✅ **Implementado el 26 Jun 2026** — ver commits para detalle.

**Contexto:** La pestaña "Sesión actual" en la sección Memoria muestra actualmente
el `session_summary` del backend, que es un dump crudo de la conversación (no un
resumen inteligente). Esto duplica la ventana de chat sin aportar valor.

---

## 1. Diagnóstico honesto

| Afirmación | Veredicto |
|---|---|
| "Un resumen LLM de la sesión mejora la experiencia" | ❌ Falso. El usuario ya ve la conversación en el chat. Un "resumen" genérico (temas: Python, flujos) es ruido no accionable. |
| "Las burbujas de chat formateadas en Session tab son útiles" | ❌ Falso. Es el mismo contenido en otra pestaña. Peor UX. |
| "El botón Editar resumen salva algo" | ❌ Falso para el usuario. Guardar un resumen editado como "hecho" no es una operación natural. |
| "Las notas automáticas (working_memory) con botón Guardar como hecho son valiosas" | ✅ Cierto. El usuario promueve información relevante a memoria persistente con un clic. |
| "El contador de mensajes + última búsqueda + duración es útil" | ✅ Cierto. Da contexto rápido sobre la sesión actual. |
| "Un historial de conversaciones pasadas con búsqueda es valioso" | ✅ Cierto. Es una necesidad real: "¿qué fue eso que me dijo sobre X la semana pasada?" |

---

## 2. Simplificación de la pestaña "Sesión actual"

### Estado actual

```
┌─ Sesión actual ─────────────────────────────┐
│  Contexto temporal — solo lectura            │
│                                              │
│  SESSION SUMMARY                             │
│  [Edit summary]                              │
│  TÚ: que puedes hacer?                       │
│  CEREBRO: Como asistente...                  │
│  TÚ: dime qué hace flujos?                   │
│  CEREBRO: La función de flujos...            │
│  ... (duplicado del chat)                    │
│                                              │
│  📝 8 mensajes · 🔍 "python básico"         │
│                                              │
│  NOTAS AUTOMÁTICAS                           │
│  • Interés: tutoriales → [📌 Guardar]       │
└──────────────────────────────────────────────┘
```

### Estado propuesto

```
┌─ Sesión actual ─────────────────────────────┐
│  Datos de esta conversación                  │
│                                              │
│  📝 8 mensajes                              │
│  🔍 Última búsqueda: "python básico"        │
│  ⏱ Chat activo desde hace 15 min            │
│                                              │
│  ┌─ Notas automáticas ──────────────────┐   │
│  │ • Interés: tutoriales → [📌 Guardar]  │   │
│  │ • Proyecto: React → [📌 Guardar]      │   │
│  │                              [📌 Todo] │   │
│  └────────────────────────────────────────┘  │
│                                              │
└──────────────────────────────────────────────┘
```

### Cambios concretos

| Acción | Archivo | Detalle |
|--------|---------|---------|
| Eliminar bloque de session_summary | `SessionTab.tsx` | Quitar parser de burbujas, quitar editor de resumen, quitar sección "SESSION SUMMARY" |
| Simplificar sección de contexto | `SessionTab.tsx` | Quitar la card adicional, subir metadata a cabecera |
| Añadir botón "Guardar todo" | `SessionTab.tsx` | Nuevo botón batch que guarda todas las notas automáticas como hechos a la vez |
| Limpiar locales | `es.json`, `en.json` | Quitar claves `edit_summary`, `edit_summary_placeholder`, `session_duration`, `session_messages` |
| Eliminar componentes no usados | Cleanup | `parseChatBlocks()`, `ChatBlock` interface |

### Comportamiento

- Si `working_memory` está vacío y no hay mensajes → mostrar empty state simple
- Si solo hay contador de mensajes (sin working_memory) → mostrar solo metadata
- "Guardar todo" guarda cada entrada de working_memory como episodio individual

---

## 3. Nueva feature: Historial de conversaciones

### Estado actual del backend (ya existe)

El backend ya tiene **todo** lo necesario menos búsqueda:

| Componente | Estado | Archivo |
|---|---|---|
| `ConversationStore` (CRUD + list_all) | ✅ Existente | `core/agents/conversation_store.py` |
| `GET /api/conversations` | ✅ Existente | `ui/tray/server.py:1819` |
| `GET /api/conversations/{id}` | ✅ Existente | `ui/tray/server.py:1838` |
| Persistencia JSON | ✅ Existente | `~/.cerebro/state/conversations/{uuid}.json` |
| Frontend `listConversations()` | ✅ Existente | `ui/tray/src/api/client.ts:301` |
| Frontend `getConversation()` | ✅ Existente | `ui/tray/src/api/client.ts:306` |
| Frontend types | ✅ Existente | `ui/tray/src/api/types.ts:106-128` |

### Lo que falta

| Componente | Estado | Archivo |
|---|---|---|
| `DELETE /api/conversations/{id}` | ❌ No existe | `ui/tray/server.py` |
| Búsqueda full-text en conversaciones | ❌ No existe | backend nuevo |
| Frontend: HistoryTab | ❌ No existe | `ui/tray/src/components/history/` |
| Frontend: HistoryStore | ❌ No existe | `ui/tray/src/stores/history.ts` |
| Frontend: ruta "history" en sidebar | ❌ No existe | `LeftSidebar.tsx`, `MainLayout.tsx` |

### Diseño propuesto

```
┌─ Historial ───────────────────────────────────┐
│                                                 │
│  🔍 [Buscar en conversaciones...]              │
│                                                 │
│  ─── Hoy ───                                   │
│                                                 │
│  🗨️ "qué puedes hacer?"           hace 2h · 3 │
│     Sobre Python y flujos                       │
│                                                 │
│  🗨️ "organiza mi semana"          hace 5h · 12│
│     Creación de eventos de calen...             │
│                                                 │
│  ─── Ayer ───                                   │
│                                                 │
│  🗨️ "busca el PDF de tesis"       hace 1d · 8 │
│     Búsqueda en documentos...                   │
│                                                 │
│  ─── 24 Jun — 25 Jun ───                        │
│                                                 │
│  🗨️ "recuérdame comprar leche"   hace 2d · 2  │
│                                                 │
│  [Cargar más]                                   │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Agrupación por fecha

- **Hoy** — conversaciones de hoy
- **Ayer** — conversaciones de ayer
- **Esta semana** — resto de la semana actual
- **[Fecha rango]** — semanas/meses anteriores
- Usar `started_at` o `last_active` del `ConversationSummary`

### Vista de detalle (al hacer clic en una conversación)

```
┌─ Historial ─────── ✕ ─────────────────────────┐
│  ← Volver                                      │
│                                                 │
│  qué puedes hacer?                              │
│  26 Jun 2026 · 3 mensajes · agente: general    │
│                                                 │
│  ┌─────────────────────────────────────────┐    │
│  │ Tú: qué puedes hacer?                   │    │
│  ├─────────────────────────────────────────┤    │
│  │ Cerebro: Como asistente personal...     │    │
│  ├─────────────────────────────────────────┤    │
│  │ Tú: dime qué hace flujos?              │    │
│  ├─────────────────────────────────────────┤    │
│  │ Cerebro: La función de flujos...        │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
│  [🗑️ Eliminar] [📌 Cargar en chat]            │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Búsqueda full-text

**Backend:** Añadir `GET /api/conversations/search?q=...` que:
1. Lista todas las conversaciones
2. Filtra aquellas donde `first_user_message` o cualquier turn content contenga el query
3. Devuelve `ConversationSummary[]` con `message_count` actualizado

**Alternativa más robusta (post-MVP):**
- Indexar en SQLite con FTS5 al escribir cada turno
- Búsqueda más rápida y precisa

### Cambios necesarios (backend)

| # | Cambio | Archivo | Esfuerzo |
|---|--------|---------|----------|
| 1 | Añadir `delete()` a `ConversationStore` | `core/agents/conversation_store.py` | 30 min |
| 2 | Añadir `DELETE /api/conversations/{id}` | `ui/tray/server.py` | 15 min |
| 3 | Añadir `GET /api/conversations/search?q=...` | `ui/tray/server.py` (o nuevo `api/conversations.py`) | 1-2h |
| 4 | Tests para search + delete | `tests/test_conversations.py` | 1h |

### Cambios necesarios (frontend)

| # | Cambio | Archivo | Esfuerzo |
|---|--------|---------|----------|
| 1 | Crear `HistoryTab.tsx` | `ui/tray/src/components/history/` | 2-3h |
| 2 | Crear `HistoryDetail.tsx` | `ui/tray/src/components/history/` | 1-2h |
| 3 | Crear `stores/history.ts` | Zustand store | 30 min |
| 4 | Añadir ruta "history" a sidebar + main layout | `LeftSidebar.tsx`, `MainLayout.tsx` | 15 min |
| 5 | Añadir `searchConversations()` a API client | `ui/tray/src/api/client.ts` | 10 min |
| 6 | Añadir tipos `ConversationSearchResult` | `ui/tray/src/api/types.ts` | 10 min |
| 7 | Añadir traducciones i18n | `es.json`, `en.json` | 15 min |

---

## 4. Integración con la pestaña de Memoria

La sección Memoria queda con 4 pestañas:

```
┌─ Memoria ─────────────────────────────────────┐
│                                                 │
│  [bookmark Hechos guardados]                    │
│  [chat Sesión actual]                           │
│  [psychology Recall]                            │
│  [history Historial]                            │
│                                                 │
└─────────────────────────────────────────────────┘
```

"Historial" es una pestaña más dentro de Memoria, misma jerarquía que las
otras tres. No añade icono al sidebar.

---

## 5. Prioridad y esfuerzo total

| Feature | Prioridad | Esfuerzo | Dependencias |
|---------|-----------|----------|--------------|
| Simplificar SessionTab | P0 — hacer ahora | ~1h | Ninguna |
| History: backend search | P1 — hacer ahora | ~2h | ConversationStore existente |
| History: frontend tab | P1 — hacer ahora | ~4h | API search existente |
| History: backend delete | P2 — opcional | ~30min | ConversationStore existente |
| History: búsqueda con SQLite FTS5 | P3 — post-MVP | ~4h | Diseño adicional |

**Total MVP (P0+P1):** ~7h

---

## 6. Riesgos

- `ConversationStore.list_all()` carga TODAS las conversaciones en memoria.
  Con uso moderado (~100 conversaciones, ~1-2MB) es irrelevante. Si crece a
  miles, habrá que paginar. Añadir `limit` y `offset` al endpoint desde el
  inicio.
- La búsqueda secuencial (`list_all` + filtro en Python) es O(n) en número de
  conversaciones. Para MVP es aceptable. Si se vuelve lento, migrar a FTS5.

---

## 7. Resumen en 3 frases

1. **Session summary se simplifica:** quitar burbujas de chat duplicadas,
   dejar metadata + notas automáticas con guardado batch.

2. **Historial de conversaciones usa infra existente:** ConversationStore,
   endpoints, types — solo falta search + frontend.

3. **Valor real:** el usuario puede buscar "¿qué me dijo sobre X?" sin tener
   el chat abierto, y promueve información útil de la sesión actual a
   memoria permanente con un clic.

---

## 8. ✅ Cambios realizados

### Simplificar SessionTab

| Acción | Archivo | Estado |
|--------|---------|--------|
| Eliminar `parseChatBlocks()`, `ChatBlock` interface, editor de resumen | `SessionTab.tsx` | ✅ |
| Simplificar layout: metadata en header, sin card extra | `SessionTab.tsx` | ✅ |
| Añadir botón "Guardar todo" (save_to_facts) batch | `SessionTab.tsx` | ✅ |
| Eliminar claves `edit_summary`, `edit_summary_placeholder` | `en.json`, `es.json` | ✅ |

### Backend — Historial

| Acción | Archivo | Estado |
|--------|---------|--------|
| Añadir `ConversationStore.delete()` | `core/agents/conversation_store.py` | ✅ |
| Añadir `DELETE /api/conversations/{id}` | `ui/tray/server.py` | ✅ |
| Añadir `GET /api/conversations/search?q=...` | `ui/tray/server.py` | ✅ |
| Tests: search + delete | `tests/test_conversations.py` | ✅ (10 tests añadidos) |

### Frontend — Historial

| Acción | Archivo | Estado |
|--------|---------|--------|
| `deleteConversation()`, `searchConversations()` | `ui/tray/src/api/client.ts` | ✅ |
| `stores/history.ts` — Zustand store | nuevo | ✅ |
| `HistoryTab.tsx` — lista con búsqueda y agrupación por fecha | nuevo | ✅ |
| `HistoryDetail.tsx` — vista detalle con mensajes y eliminar | nuevo | ✅ |
| Pestaña "History" en MemoryView (4 tabs) | `MemoryViewContent.tsx` | ✅ |
| Traducciones EN/ES | `en.json`, `es.json` | ✅ |

### Tests

```bash
pytest tests/test_conversations.py -x -v  # 20 passed
npx tsc --noEmit                            # 0 errors in memory/ components
```
