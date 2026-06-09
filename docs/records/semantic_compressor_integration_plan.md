# ⚡ PLAN MODULAR DE INTEGRACIÓN Y PRODUCCIÓN: SEMANTIC CONTEXT COMPRESSOR

Este documento contiene el plan maestro estructurado en pasos atómicos para que **Claude Code** complete la integración del compresor de contexto semántico en el pipeline de producción del proyecto. Cada paso está diseñado para ser autocontenido, minimizando el riesgo de regresiones y asegurando la estabilidad del sistema.

---

## 📋 INSTRUCCIONES DE USO PARA CLAUDE CODE
1. Copia y pega **un solo paso a la vez** en la consola de Claude Code.
2. Espera a que termine, ejecute los tests correspondientes y marque el paso como completado cambiando el estado de `[ ]` a `[x]` en la sección **"Tabla de Control de Progreso"** al final de este archivo.
3. No avances al siguiente paso hasta que el paso actual esté marcado como **DONE**.

---

### 🛠️ PASO 1: Corrección de Deprecación de Python 3.14 (`core/utils/compressor.py`)

**Objetivo:** Reemplazar el uso de `asyncio.iscoroutinefunction()` por la biblioteca nativa `inspect` para evitar fallos futuros en entornos con Python modernos (3.14+ / 3.16).

**Instrucciones para Claude Code:**

```text
Tarea: Corregir el Deprecation Warning en core/utils/compressor.py relacionado con la detección de funciones corrutinas.

1. Abre el archivo `core/utils/compressor.py`.
2. Asegúrate de que el módulo `inspect` esté importado en la parte superior del archivo (`import inspect`).
3. Busca la línea cercana a la 105 (o donde se valide si la función de embedding es asíncrona) que utilice:
   asyncio.iscoroutinefunction(...)
4. Modifícala para usar la alternativa moderna y recomendada:
   inspect.iscoroutinefunction(...)
5. Guarda el archivo. Ejecuta la suite de pruebas automatizadas con pytest para garantizar que la detección sigue funcionando perfectamente.
6. Una vez validado, abre `semantic_compressor_integration_plan.md`, busca la sección de "Tabla de Control de Progreso" al final del archivo, y cambia el estado del Paso 1 a "[x] DONE".
```

---

### 🛠️ PASO 2: Ajuste del Presupuesto de Tokens y Parámetros Flexibles

**Objetivo:** Ajustar el límite por defecto `max_tokens=600` a un valor más equilibrado (800 o 1000) para evitar recortes agresivos en consultas extensas, permitiendo configurarlo dinámicamente.

**Instrucciones para Claude Code:**

```text
Tarea: Modificar el presupuesto por defecto de tokens en `SemanticCompressor` para evitar un filtrado excesivamente agresivo.

1. Abre el archivo `core/utils/compressor.py`.
2. Localiza la definición de la clase `SemanticCompressor` y su método constructor `__init__`.
3. Si el parámetro `max_tokens` (o el límite del presupuesto del token assembler) está fijado estrictamente en 600, actualiza el valor por defecto a 800 (o un rango seguro entre 800 y 1000 que maneje cómodamente de 3 a 5 chunks de 6 oraciones).
4. Asegúrate de que este valor sea parametrizable a través del constructor para conservar la flexibilidad en las pruebas de estrés.
5. Corre los tests de tokens (`manual_tests/compressor/bench_tokens.py` o similares) para validar que el nuevo presupuesto de tokens se respete sin cortes abruptos.
6. Una vez terminado, abre `semantic_compressor_integration_plan.md` y marca el Paso 2 como "[x] DONE" en la tabla de progreso.
```

---

### 🛠️ PASO 3: Activación de la Bandera de Compresión para el Frontend

**Objetivo:** Asegurar que cuando el contexto sea procesado y optimizado por el compresor, la propiedad `documents_compressed` de la entidad de retorno se establezca en `True`. Esto habilitará el badge visual "Compressed ⚡" en el panel de fuentes de la UI.

**Instrucciones para Claude Code:**

```text
Tarea: Asegurar el flujo del metadato de compresión para activar el indicador visual del frontend.

1. Identifica dónde se instancia o devuelve el objeto `AssembledContext` dentro de tu lógica de compresión o en `query_engine.py`.
2. Localiza el bloque exacto de código donde el `SemanticCompressor` reduce los chunks y ensambla la respuesta final.
3. Añade la asignación explícita para que `assembled_context.documents_compressed = True` se active únicamente cuando el compresor haya ejecutado con éxito el filtrado de oraciones/chunks.
4. Si la reducción no se aplica (por ejemplo, si el presupuesto de tokens original ya era inferior al límite), asegúrate de mantenerlo en `False` o manejarlo de manera condicional según corresponda.
5. Guarda los cambios y ejecuta pruebas unitarias para validar que el objeto de salida contenga la propiedad `documents_compressed: true`.
6. Al finalizar, abre `semantic_compressor_integration_plan.md` y marca el Paso 3 como "[x] DONE" en la tabla de progreso.
```

---

### 🛠️ PASO 4: Instanciación e Inyección en Producción (`main.py` / `server.py`)

**Objetivo:** Activar el compresor en el flujo real de la aplicación instanciándolo con Path B (TF-IDF) por defecto, inyectándolo directamente en el `RAGQueryEngine`.

**Instrucciones para Claude Code:**

```text
Tarea: Activar el SemanticCompressor con Path B (TF-IDF) por defecto en el arranque oficial de la producción.

1. Abre el archivo principal de inicialización del servidor (típicamente `main.py` o la sección de inicialización de estados de `server.py`).
2. Importa la clase del compresor:
   from core.utils.compressor import SemanticCompressor
3. Localiza el punto exacto del ciclo de vida donde se inicializa la instancia de `RAGQueryEngine`.
4. Modifica la instanciación inyectando el compresor usando Path B (TF-IDF), pasando `embed_fn=None` para evitar dependencias obligatorias del servidor de embeddings de llama.cpp en operaciones estándar:
   compressor = SemanticCompressor(embed_fn=None)
   rag_engine = RAGQueryEngine(store=store, engine=engine, compressor=compressor)
5. Levanta el servidor localmente en el puerto de desarrollo (7842) y asegúrate de que no existan errores de importación circular o fallos catastróficos en el booteo.
6. Al finalizar con éxito, abre `semantic_compressor_integration_plan.md` y marca el Paso 4 como "[x] DONE" en la tabla de progreso.
```

---

### 🛠️ PASO 5: Soporte Multi-Puerto para Path A (Servidor de Embeddings Dedicado)

**Objetivo:** Permitir que el compresor apunte opcionalmente a un servidor llama.cpp dedicado exclusivamente a embeddings (Puerto 8082) mediante variables de entorno o configuraciones del sistema, aislando el tráfico del motor de chat estándar (Puerto 8080).

**Instrucciones para Claude Code:**

```text
Tarea: Agregar flexibilidad de configuración para el Path A (Neural Scoring) usando un puerto de servicio de embeddings aislado.

1. Abre los archivos de configuración del entorno o el constructor correspondiente donde se define la URL base para las llamadas de embeddings de `InferenceEngine` o `SemanticCompressor`.
2. Permite leer una variable de entorno como `LLAMACPP_EMBED_URL` o configurar por defecto `http://127.0.0.1:8082` cuando se active explícitamente el Path A.
3. Asegúrate de que si esta URL/función opcional no está configurada, el sistema degrade con elegancia (*graceful fallback*) hacia Path B (TF-IDF) de forma automática en lugar de lanzar excepciones de conexión.
4. Agrega un log con loguru indicando qué vía de compresión se ha inicializado en el arranque (`[INFO] SemanticCompressor inicializado usando Path B (TF-IDF)` o `Path A (Neural)`).
5. Abre `semantic_compressor_integration_plan.md` y marca el Paso 5 como "[x] DONE" en la tabla de progreso.
```

---

### 🛠️ PASO 6: Ejecución Final de la Suite de Regresión Completa

**Objetivo:** Validar que la totalidad de los componentes del sistema sigan operativos tras la integración del compresor, verificando tiempos de respuesta y ratios de compresión.

**Instrucciones para Claude Code:**

```text
Tarea: Ejecutar control de calidad final del sistema post-integración.

1. Corre toda la suite de pruebas automatizadas del proyecto utilizando tu comando estándar de pytest:
   pytest
2. Asegúrate de que los 24/24 tests pasen exitosamente con cero regresiones detectadas.
3. Ejecuta los benchmarks específicos de latencia (`manual_tests/compressor/bench_latency.py`) para comprobar que el overhead en producción de Path B se mantiene en la escala de ~2-3ms y que se preserva la reducción global de latencia en las consultas RAG.
4. Una vez verificado el comportamiento óptimo y estable de toda la aplicación, abre `semantic_compressor_integration_plan.md` y marca el Paso 6 como "[x] DONE".
```

---

## 📈 TABLA DE CONTROL DE PROGRESO

Usa esta lista para realizar el seguimiento del proceso de desarrollo asíncrono con Claude Code.

- [x] Paso 1: Corrección de Deprecación de Python 3.14 (`core/utils/compressor.py`)
- [x] Paso 2: Ajuste del Presupuesto de Tokens y Parámetros Flexibles
- [x] Paso 3: Activación de la Bandera de Compresión para el Frontend
- [x] Paso 4: Instanciación e Inyección en Producción (`main.py` / `server.py`)
- [x] Paso 5: Soporte Multi-Puerto para Path A (Servidor de Embeddings Dedicado)
- [x] Paso 6: Ejecución Final de la Suite de Regresión Completa

---

Fin del plan modular de integración.
