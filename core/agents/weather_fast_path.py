from __future__ import annotations

import json
import re

import httpx

_WTHR_URL = "https://wttr.in"

_WEATHER_RE = re.compile(
    r"\b(?:weather|climate|clima|temperatura|"
    r"pron[oó]stico\s+(?:del\s+)?tiempo|"
    r"c[oó]mo\s+est[aá]\s+(?:el\s+)?(?:clima|tiempo)|"
    r"qu[eé]\s+tal\s+(?:el\s+)?(?:clima|tiempo)|"
    r"qu[eé]\s+tiempo\s+hace|"
    r"how('s| is) the weather|"
    r"what('s| is) the (weather|temperature|forecast)|"
    r"is it (cold|hot|warm|rainy|sunny|cloudy|windy)|"
    r"weather\s+(?:in|for|at|of))\b",
    re.IGNORECASE,
)

_LOCATION_RE = re.compile(
    r"(?:en|in|at|for|de|del|para)\s+"
    r"([A-Za-zÁÉÍÓÚáéíóúñÑ][A-Za-zÁÉÍÓÚáéíóúñÑ\s.-]+)"
    r"(?:\s*(?:hoy|mañana|ahora|now|today|tomorrow|ayer|yesterday|"
    r"esta\s+semana|this\s+weekend|este\s+fin\s+de\s+semana|"
    r"[?.!]|$))",
    re.IGNORECASE,
)

_CITY_WORDS = frozenset(
    {
        "weather",
        "clima",
        "tiempo",
        "temperatura",
        "pronóstico",
        "forecast",
        "hoy",
        "today",
        "mañana",
        "tomorrow",
        "ayer",
        "yesterday",
        "ahora",
        "now",
        "semana",
        "week",
        "weekend",
        "finde",
        "qué",
        "que",
        "how",
        "what",
        "is",
        "the",
        "en",
        "in",
        "at",
        "for",
        "de",
        "del",
        "para",
        "esta",
        "este",
        "el",
        "la",
        "las",
    }
)


def _extract_location(query: str) -> str:
    m = _LOCATION_RE.search(query)
    if m:
        candidate = m.group(1).strip().rstrip(".,!?")
        words = candidate.split()
        filtered = [w for w in words if w.lower() not in _CITY_WORDS]
        if filtered:
            return " ".join(filtered).strip()
    return ""


def _format_weather(data: dict) -> str:
    try:
        cc = data.get("current_condition", [{}])[0]
        desc = (cc.get("weatherDesc", [{}])[0].get("value", "") or "unknown").capitalize()
        temp_c = cc.get("temp_C", "?")
        temp_f = cc.get("temp_F", "?")
        feels_c = cc.get("FeelsLikeC", temp_c)
        humidity = cc.get("humidity", "?")
        wind = cc.get("windspeedKmph", "?")
        uv = cc.get("uvIndex", "?")
        lines = [
            f"🌡 {temp_c}°C ({temp_f}°F) — {desc}",
            f"Sensación térmica: {feels_c}°C",
            f"💧 Humedad: {humidity}%",
            f"💨 Viento: {wind} km/h",
            f"☀️ Índice UV: {uv}",
        ]
        return "\n".join(lines)
    except (KeyError, IndexError):
        return "No se pudo interpretar la respuesta del clima."


def try_weather_fast_path(query: str) -> str | None:
    if not _WEATHER_RE.search(query):
        return None

    location = _extract_location(query)
    if not location:
        location = _detect_location_from_query(query)

    if not location:
        return _weather_no_location()

    try:
        resp = httpx.get(
            f"{_WTHR_URL}/{location}?format=j1",
            timeout=10.0,
            headers={"User-Agent": "curl/8.0"},
        )
        resp.raise_for_status()
        data = resp.json()
        location_name = (
            data.get("nearest_area", [{}])[0].get("areaName", [{}])[0].get("value", location)
        )
        lines = [f"**Clima en {location_name}**"]
        lines.append(_format_weather(data))
        return "\n".join(lines)
    except httpx.HTTPError:
        return _weather_error(location)
    except (json.JSONDecodeError, KeyError, IndexError):
        return _weather_error(location)


def _detect_location_from_query(query: str) -> str:
    q = query.strip()
    q = _WEATHER_RE.sub("", q).strip()
    q = re.sub(r"[?.!,\s]+$", "", q).strip()
    if q and not _CITY_WORDS.intersection(q.lower().split()):
        return q
    return ""


def _weather_no_location() -> str:
    return "¿De qué ciudad quieres saber el clima? " "Ej: 'clima en Madrid' o 'weather in London'."


def _weather_error(location: str) -> str:
    return f"No pude obtener el clima para '{location}'. Verifica el nombre de la ciudad."
