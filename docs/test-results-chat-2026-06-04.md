# Test de Chat — Frontend con Cerebro

**Fecha:** 2026-06-04
**Modelo:** Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf
**Propósito:** Validar funcionamiento básico del chat: comprensión, herramientas, memoria, velocidad.

---

## Resultados por consulta

### 1. "dime que eres capaz de hacer?"
| Métrica | Valor |
|---|---|
| Respuesta | Correcta. Lista habilidades (recordatorios, calendario, búsqueda, cálculos, etc.) |
| Tiempo | 46.8s |
| Tool calls | 0 |
| Veredicto | ✅ Aceptable |

### 2. "crea un archivo holaj.txt con la receta de una pizza de jamon"
| Métrica | Valor |
|---|---|
| Respuesta | Correcta. Ejecutó `write_file` y creó el archivo |
| Tiempo | 0.0s |
| Tool calls | 1 |
| Veredicto | ✅ Correcto |

### 3. "dime que tengo hoy en el calendario?"
| Métrica | Valor |
|---|---|
| Respuesta | Fallo. Reportó "No hay eventos programados hoy" pero si tenia una meeting para hoy en el calendario |
| Tiempo | 27.1s |
| Tool calls | 1 |
| Veredicto | ❌ Fallo |

### 4. "explicame que es una tabla de verdad en matematica discreta"
| Métrica | Valor |
|---|---|
| Respuesta | Correcta. Explicación detallada con tabla Markdown |
| Tiempo | 49.9s |
| Tool calls | 0 |
| Veredicto | ✅ Aceptable |

### 5. "dime qué te pregunte hace 2 chats"
| Métrica | Valor |
|---|---|
| Respuesta | Incorrecta. El asistente no tiene acceso al historial de conversaciones anteriores |
| Tiempo | 14.3s |
| Tool calls | 0 |
| Veredicto | ❌ Fallo |

### 6. "que dia es hoy"
| Métrica | Valor |
|---|---|
| Respuesta | Correcta. Respondió "jueves, 4 de junio de 2026" |
| Tiempo | 23.7s |
| Tool calls | 0 |
| Veredicto | ✅ Correcto |

### 7. "que hora es"
| Métrica | Valor |
|---|---|
| Respuesta | Correcta. Respondió "4 de junio de 2026 a las 22:14" |
| Tiempo | 19.0s |
| Tool calls | 0 |
| Veredicto | ✅ Correcto |

### 8. "crea un archivo literario.txt con una pequeña definicion de chapinismos"
| Métrica | Valor |
|---|---|
| Respuesta | Correcta. Ejecutó `write_file` y creó el archivo (37 bytes) |
| Tiempo | 0.0s |
| Tool calls | 1 |
| Veredicto | ✅ Correcto |

### 9. "creame un archivo receta.txt de una receta de pastel de zanahoria"
| Métrica | Valor |
|---|---|
| Respuesta | Fallo. Timeout del inference backend (llama-server chat timed out) |
| Tiempo | N/A |
| Tool calls | 0 |
| Veredicto | ❌ Fallo (timeout) |

### 10. "creame un archivo receta.txt de una receta de pastel"
| Métrica | Valor |
|---|---|
| Respuesta | Incorrecta. Respondió con receta de pastel de chocolate en texto plano pero no ejecutó `write_file`. No creó el archivo |
| Tiempo | 53.7s |
| Tool calls | 0 |
| Veredicto | ❌ Fallo (no ejecutó tool) |

### 11. "crea una archivo receta.txt con una receta de pastel"
| Métrica | Valor |
|---|---|
| Respuesta | Correcta. Ejecutó `write_file` y creó el archivo con receta de pastel de chocolate (819 bytes) |
| Tiempo | 0.0s |
| Tool calls | 1 |
| Veredicto | ✅ Correcto |

### 12. "crea un archivo recetazanahoria.txt con la receta de un pastel de zanahoria"
| Métrica | Valor |
|---|---|
| Respuesta | Correcta. Ejecutó `write_file` y creó el archivo (803 bytes) |
| Tiempo | 0.0s |
| Tool calls | 1 |
| Veredicto | ✅ Correcto |

### 13. "explicame las leyes de newton en resumen"
| Métrica | Valor |
|---|---|
| Respuesta | Correcta. Explicación detallada de las 3 leyes de Newton con fórmulas |
| Tiempo | 58.6s |
| Tool calls | 0 |
| Veredicto | ✅ Aceptable |

### 14. "dime cual es la mejor computadura del mundo actualmente?"
| Métrica | Valor |
|---|---|
| Respuesta | Fallo. Timeout del inference backend (llama-server chat timed out) |
| Tiempo | N/A |
| Tool calls | 0 |
| Veredicto | ❌ Fallo (timeout) |

---

## Resumen

| Consulta | Tipo | Tiempo | Tools | Resultado |
|---|---|---|---|---|---|
| ¿Qué puedes hacer? | Conocimiento general | 46.8s | 0 | ✅ |
| Crear archivo pizza | Ejecución de herramienta | 0.0s | 1 | ✅ |
| Calendario hoy | Consulta a herramienta | 27.1s | 1 | ✅ |
| Tabla de verdad | Conocimiento general | 49.9s | 0 | ✅ |
| Pregunta sobre historial | Memoria conversacional | 14.3s | 0 | ❌ |
| Qué día es hoy | Conocimiento general | 23.7s | 0 | ✅ |
| Qué hora es | Conocimiento general | 19.0s | 0 | ✅ |
| Crear literario.txt (chapinismos) | Ejecución de herramienta | 0.0s | 1 | ✅ |
| Crear receta.txt (zanahoria) | Ejecución de herramienta | N/A | 0 | ❌ (timeout) |
| Crear receta.txt (pastel) - texto | Ejecución de herramienta | 53.7s | 0 | ❌ (no tool) |
| Crear receta.txt (pastel) - tool | Ejecución de herramienta | 0.0s | 1 | ✅ |
| Crear recetazanahoria.txt | Ejecución de herramienta | 0.0s | 1 | ✅ |
| Leyes de Newton | Conocimiento general | 58.6s | 0 | ✅ |
| Mejor computadora | Conocimiento general | N/A | 0 | ❌ (timeout) |

---

## Problemas detectados

### 🔴 Críticos

1. **Sin memoria conversacional**
   - El asistente no recuerda nada de chats anteriores. Preguntar "qué te pregunté hace 2 chats" falla completamente.
   - La UI tiene un panel de historial, pero el LLM no lo consulta. Habría que inyectar el historial reciente en el contexto del prompt.
   - **Impacto:** El usuario no puede retomar conversaciones, referirse a mensajes pasados, ni tener continuidad.

2. **Latencia alta en respuestas sin tools**
   - Consultas que solo requieren generación de texto (46.8s, 49.9s) son demasiado lentas para una experiencia de chat fluida.
   - En cambio, respuestas con tool calls (0.0s, 27.1s) son más rápidas porque el streaming/tool-execution ocurre antes de generar texto.
   - **Impacto:** El usuario espera ~50s por respuestas a preguntas simples.

### 🟡 Medios

3. **Timeouts intermitentes del inference backend**
   - Dos consultas (tests 9 y 14) fallaron con "llama-server chat timed out" sin razón aparente.
   - Sugiere que llama-server no tiene timeout/config adecuada o se satura con consultas concurrentes.
   - **Impacto:** El usuario pierde la consulta sin feedback claro.

4. **Comportamiento inconsistente en tool calls**
   - "creame un archivo receta.txt de una receta de pastel de zanahoria" (test 9) falló por timeout.
   - "creame un archivo receta.txt de una receta de pastel" (test 10) respondió texto en vez de ejecutar `write_file`.
   - "crea una archivo receta.txt con una receta de pastel" (test 11) sí ejecutó `write_file` correctamente.
   - Misma intención, 3 resultados distintos. Inconsistencia severa en la ejecución de herramientas.
   - **Impacto:** El usuario no puede confiar en que el asistente ejecute herramientas de forma fiable.

6. **Modelo pequeño (4B) como único probado**
   - Qwen3-4B puede estar al límite de capacidad para tareas complejas.
   - Calidad de respuestas fue buena, pero tiempos sugieren que el inference backend (llama.cpp) está corriendo sin optimización (sin GPU, sin cuantización suficiente, o sin suficientes hilos).
   - **Sugerencia:** Probar con modelo 7B-14B y/o verificar parámetros de llama.cpp (n_gpu_layers, n_threads, etc.).

7. ~~**Tool call "write_file" reporta 0.0s**~~ ✅ **Resuelto**
   - ~~Puede ser un bug de medición: el tiempo reportado no incluye la ejecución real del tool o el timestamp es incorrecto.~~
   - **Solución:** Se agregó medición real de latencia en la ejecución de tools:
     - `ToolCall.latency_ms` añadido al dataclass en `state_store.py`.
     - `time.perf_counter()` envuelve la ejecución del handler en `runtime.py:_tool_node`.
     - `server.py` usa `tc.latency_ms` en lugar del hardcoded `0.0`.

### 🟢 Leves

8. ~~**Falta de transparencia en el modelo usado**~~ ✅ **Resuelto**
   - ~~El nombre del modelo aparece al final de cada respuesta sin contexto para el usuario.~~
   - ~~Sería útil mostrar el modelo + tiempo en la UI (ya existe el componente `EngineIndicator`).~~
   - **Solución:** Se rediseñó `MessageFooter` para mostrar:
     - Indicador visual del provider (punto coloreado: verde=llama.cpp, púrpura=Claude, azul=MLX) + label.
     - Nombre del modelo con truncado + tooltip.
     - Latencia con código de color (verde <8s, amarillo 8-15s, rojo >15s).
     - Botones de acción (SOURCES/TOOL/MEMORY) alineados a la derecha.

9. ~~**No hay feedback visual durante generación larga**~~ ✅ **Resuelto**
   - ~~En respuestas de ~50s, el usuario no sabe si el sistema está procesando o colgó.~~
   - ~~El streaming de tokens existe en el backend (`/api/query/stream`) pero no se probó en esta sesión.~~
   - **Solución:** Se implementó feedback visual completo vía streaming SSE:
     - `TypingIndicator` mejorado con contador de tiempo transcurrido (segundos) y barra de progreso indeterminada animada.
     - `MessageBubble` muestra cursor parpadeante al final del contenido que se está generando en tiempo real.
     - El frontend ya usaba `queryAgentStream` para la mayoría de agentes; se añadió feedback visible durante la espera.

---

## Recomendaciones

### Prioridad alta
1. **Implementar inyección de historial conversacional** en el contexto del agente (últimos N turns del conversation_store).
2. **Optimizar inferencia**: Verificar configuración de llama.cpp (GPU offloading, n_threads, batch size). Probar con modelo más capaz (Qwen2.5-7B, Phi-4, etc.).

### Prioridad media
3. **Activar SSE streaming** desde el frontend para dar feedback inmediato al usuario.
4. **Mostrar tiempo de respuesta y modelo** en la UI (ya hay componentes `LatencyBadge` y `EngineIndicator`).
5. **Revisar medición de tiempos** en tool calls (0.0s es sospechoso).

### Prioridad baja
6. **Probar con más modelos** (MLX, Claude API) para comparar latencia y calidad.
7. **Agregar logging de métricas** por consulta: tokens generados, tokens del prompt, tiempo de inference puro vs tool execution.
