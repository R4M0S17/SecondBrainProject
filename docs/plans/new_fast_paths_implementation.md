# New Deterministic Fast Paths — Implementación

> **Fecha:** 2026-06-15
> **Estado:** ✅ Completado

---

## Resumen

Se implementaron 4 nuevos fast paths deterministas (sin LLM) para consultas comunes:

1. **Weather (Clima)** — API `wttr.in`, sin API key
2. **Dictionary (Diccionario)** — API `dictionaryapi.dev`, sin API key
3. **Unit Conversion (Conversión de unidades)** — Conversión local en Python
4. **System Info (Información del sistema)** — `psutil` + `platform`

---

## Orden canónico actualizado

```
time_date → weather → dictionary → config_read → system_info → url_open → web_search → math → unit_conversion → file_write → reminder → calendar_read → calendar_write → file_search
```

---

## Archivos creados

| Archivo | Descripción | Líneas |
|---------|-------------|--------|
| `core/agents/weather_fast_path.py` | Clima vía wttr.in. Detecta consultas en ES/EN. Extrae ciudad de la query. | ~130 |
| `core/agents/dictionary_fast_path.py` | Definiciones vía dictionaryapi.dev. Soporta ES/EN, quick commands (`def <word>`). | ~105 |
| `core/agents/unit_conversion_fast_path.py` | Conversión local: longitud, peso, temperatura, volumen, tiempo, velocidad. | ~220 |
| `core/agents/system_info_fast_path.py` | RAM, CPU, disco, uptime, versión macOS vía psutil+platform. | ~155 |
| `tests/test_fast_paths_new.py` | 23 tests (19 sin red, 2 con red, 2 de integración con router). | ~245 |

## Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `core/agents/fast_path_router.py` | `FastPathKind` extendido con `weather`, `dictionary`, `unit_conversion`, `system_info`. Nuevos métodos `_try_weather`, `_try_dictionary`, `_try_system_info`, `_try_unit_conversion`. Importaciones añadidas. |
| `core/agents/runtime.py` | `_apply_fast_path_result` soporta los 4 nuevos `kind`. |

---

## Detalles de implementación

### Weather (`weather_fast_path.py`)
- **API:** `wttr.in/{city}?format=j1` (JSON, sin API key)
- **Detección:** Regex ES/EN para clima, temperatura, pronóstico
- **Extracción de ciudad:** Busca después de "en/in/at/for/de/del/para", o deduce del resto de la query
- **Formato:** Temperatura °C/°F, sensación térmica, humedad, viento, UV

### Dictionary (`dictionary_fast_path.py`)
- **API:** `api.dictionaryapi.dev/api/v2/entries/en/{word}` (sin API key)
- **Detección:** `define X`, `qué significa X`, `what is the meaning of X`, `def X` (quick)
- **Formato:** Palabra con fonética, origen, parte del discurso, definición, ejemplo, sinónimos

### Unit Conversion (`unit_conversion_fast_path.py`)
- **Sin API:** conversión local con factores fijos
- **Unidades:** longitud (km,m,cm,mm,mi,yd,ft,in), peso (kg,g,mg,lb,oz), temperatura (C,F,K), volumen (l,ml,gal), tiempo (s,min,h,día,semana), velocidad (km/h, mph, m/s)
- **Detección:** `convertir X a Y`, `cuánto es X en Y`, `X [unidad] to [unidad]`

### System Info (`system_info_fast_path.py`)
- **Fuente:** `psutil` (RAM, CPU, disco, uptime) + `platform` (SO, arquitectura) + `sw_vers` (versión macOS)
- **Consultas específicas:** `How much RAM`, `CPU info`, `disk space`, `uptime`, `diagnóstico del sistema`
- **Diagnóstico completo:** `system info`, `diagnóstico` — muestra RAM + CPU + disco + sistema + uptime

---

## Tests

```
tests/test_fast_paths_new.py — 19 tests sin red + 2 tests de integración con router
tests/test_fast_path_router.py — 6 tests (sin cambios, siguen pasando)
```

Los 2 tests con `@pytest.mark.network` requieren conexión a internet (weather API, dictionary API).

**Tests que deben pasar:** `tests/test_fast_path_router.py` (6) + `tests/test_fast_paths_new.py` (21 sin red) + todos los tests existentes.
