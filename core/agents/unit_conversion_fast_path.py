from __future__ import annotations

import re

_CONVERT_RE = re.compile(
    r"\b(?:convert(?:ir)?|"
    r"c[uaá]nto\s+(?:es|son|vale)|"
    r"c[oó]mo\s+(?:es|son)|"
    r"cu[áa]ntos?\s+\w+|"
    r"\d+\s+\w+\s+(?:a|to|en|por)\s+\w+)",
    re.IGNORECASE,
)

_NUMBER_RE = re.compile(r"(-?\d+(?:[.,]\d+)?)")

_LENGTH_UNITS = {
    "km": 1000.0,
    "kilometro": 1000.0,
    "kilómetro": 1000.0,
    "kilometros": 1000.0,
    "kilómetros": 1000.0,
    "m": 1.0,
    "metro": 1.0,
    "metros": 1.0,
    "cm": 0.01,
    "centimetro": 0.01,
    "centímetro": 0.01,
    "centimetros": 0.01,
    "centímetros": 0.01,
    "mm": 0.001,
    "milimetro": 0.001,
    "milímetro": 0.001,
    "milimetros": 0.001,
    "milímetros": 0.001,
    "mi": 1609.34,
    "milla": 1609.34,
    "millas": 1609.34,
    "yd": 0.9144,
    "yarda": 0.9144,
    "yardas": 0.9144,
    "ft": 0.3048,
    "pie": 0.3048,
    "pies": 0.3048,
    "in": 0.0254,
    "pulgada": 0.0254,
    "pulgadas": 0.0254,
    "inch": 0.0254,
    "inches": 0.0254,
}

_WEIGHT_UNITS = {
    "kg": 1.0,
    "kilo": 1.0,
    "kilos": 1.0,
    "kilogramo": 1.0,
    "kilogramos": 1.0,
    "g": 0.001,
    "gramo": 0.001,
    "gramos": 0.001,
    "mg": 1e-6,
    "miligramo": 1e-6,
    "miligramos": 1e-6,
    "lb": 0.453592,
    "libra": 0.453592,
    "libras": 0.453592,
    "oz": 0.0283495,
    "onza": 0.0283495,
    "onzas": 0.0283495,
}

_TEMP_CONVERT = {
    ("celsius", "fahrenheit"): lambda c: c * 9 / 5 + 32,
    ("celsius", "kelvin"): lambda c: c + 273.15,
    ("fahrenheit", "celsius"): lambda f: (f - 32) * 5 / 9,
    ("fahrenheit", "kelvin"): lambda f: (f - 32) * 5 / 9 + 273.15,
    ("kelvin", "celsius"): lambda k: k - 273.15,
    ("kelvin", "fahrenheit"): lambda k: (k - 273.15) * 9 / 5 + 32,
}

_VOLUME_UNITS = {
    "l": 1.0,
    "litro": 1.0,
    "litros": 1.0,
    "ml": 0.001,
    "mililitro": 0.001,
    "mililitros": 0.001,
    "gal": 3.78541,
    "galon": 3.78541,
    "galón": 3.78541,
    "galones": 3.78541,
}

_TIME_UNITS = {
    "segundo": 1,
    "segundos": 1,
    "second": 1,
    "seconds": 1,
    "minuto": 60,
    "minutos": 60,
    "minute": 60,
    "minutes": 60,
    "hora": 3600,
    "horas": 3600,
    "hour": 3600,
    "hours": 3600,
    "día": 86400,
    "días": 86400,
    "dia": 86400,
    "dias": 86400,
    "day": 86400,
    "days": 86400,
    "semana": 604800,
    "semanas": 604800,
    "week": 604800,
    "weeks": 604800,
}

_SPEED_UNITS = {
    "km/h": 1.0,
    "kmh": 1.0,
    "kph": 1.0,
    "kilometro por hora": 1.0,
    "kilómetro por hora": 1.0,
    "kilometros por hora": 1.0,
    "kilómetros por hora": 1.0,
    "mph": 1.60934,
    "mi/h": 1.60934,
    "milla por hora": 1.60934,
    "millas por hora": 1.60934,
    "m/s": 3.6,
    "ms": 3.6,
    "metro por segundo": 3.6,
    "metros por segundo": 3.6,
}

_ALL_CATEGORIES: list[tuple[str, dict[str, float], str]] = [
    ("length", _LENGTH_UNITS, "m"),
    ("weight", _WEIGHT_UNITS, "kg"),
    ("volume", _VOLUME_UNITS, "l"),
    ("time", _TIME_UNITS, "s"),
    ("speed", _SPEED_UNITS, "km/h"),
]


def _normalize_unit(name: str) -> str:
    u = name.lower().strip()
    replacements = {
        "centigrados": "celsius",
        "centígrados": "celsius",
        "farenheit": "fahrenheit",
        "km": "km",
        "kmh": "km/h",
        "kph": "km/h",
        "ms": "m/s",
        "pound": "lb",
        "pounds": "lb",
        "lbs": "lb",
        "ounce": "oz",
        "ounces": "oz",
        "inch": "in",
        "inches": "in",
        "feet": "ft",
        "foot": "ft",
        "yard": "yd",
        "yards": "yd",
        "mile": "mi",
        "miles": "mi",
        "gallon": "gal",
        "gallons": "gal",
        "liter": "l",
        "liters": "l",
        "litre": "l",
        "litres": "l",
        "kilogram": "kg",
        "kilograms": "kg",
        "gram": "g",
        "grams": "g",
        "milligram": "mg",
        "milligrams": "mg",
        "millimeter": "mm",
        "millimeters": "mm",
        "milímetro": "mm",
        "milímetros": "mm",
        "centimeter": "cm",
        "centimeters": "cm",
        "centímetro": "cm",
        "centímetros": "cm",
        "kilometer": "km",
        "kilometers": "km",
        "kilómetro": "km",
        "kilómetros": "km",
        "meter": "m",
        "meters": "m",
        "metro": "m",
        "metros": "m",
        "hour": "h",
        "hours": "h",
        "hora": "h",
        "horas": "h",
        "minute": "min",
        "minutes": "min",
        "minuto": "min",
        "minutos": "min",
        "second": "s",
        "seconds": "s",
        "segundo": "s",
        "segundos": "s",
    }
    return replacements.get(u, u)


_TEMP_NAMES = {"celsius", "fahrenheit", "kelvin", "centigrados", "centígrados", "farenheit"}


def _find_category(unit: str) -> tuple[str, dict[str, float], str] | None:
    if unit in _TEMP_NAMES:
        return (
            "temperature",
            {
                "celsius": 1.0,
                "fahrenheit": 1.0,
                "kelvin": 1.0,
                "centigrados": 1.0,
                "centígrados": 1.0,
                "farenheit": 1.0,
            },
            unit,
        )
    for cat, units, _ in _ALL_CATEGORIES:
        if unit in units:
            return cat, units, unit
    return None


def _convert_value(value: float, from_unit: str, to_unit: str) -> str | None:
    fn = _TEMP_CONVERT.get((from_unit, to_unit))
    if fn:
        result = fn(value)
        return (
            f"{_fmt(value)}° {from_unit.capitalize()} = **{_fmt(result)}° {to_unit.capitalize()}**"
        )

    fcat = _find_category(from_unit)
    tcat = _find_category(to_unit)
    if fcat and tcat and fcat[0] == tcat[0]:
        _, fmap, _ = fcat
        _, tmap, _ = tcat
        base = value * fmap[from_unit]
        result = base / tmap[to_unit]
        return f"{_fmt(value)} {from_unit} = **{_fmt(result)} {to_unit}**"

    return None


def _fmt(n: float) -> str:
    rounded = round(n, 6)
    if rounded.is_integer():
        return str(int(rounded))
    text = f"{rounded:.6f}".rstrip("0").rstrip(".")
    return text


_SEPARATORS = frozenset({"a", "to", "en", "por"})


def _extract_conversion(query: str) -> tuple[float, str, str] | None:
    q = query.lower()
    nums = _NUMBER_RE.findall(q)
    if not nums:
        return None
    value = float(nums[0].replace(",", "."))

    words = q.split()
    from_unit = None
    to_unit = None
    seen_to = False

    for w in words:
        normalized = _normalize_unit(w)
        if normalized in _SEPARATORS:
            seen_to = True
            continue
        if seen_to and normalized not in _SEPARATORS and len(normalized) > 1:
            tcat = _find_category(normalized)
            if tcat:
                to_unit = normalized
                break

    before = words[:]
    for sep in _SEPARATORS:
        if sep in words:
            before = words[: words.index(sep)]
            break
    for w in reversed(before):
        normalized = _normalize_unit(w)
        if normalized and normalized not in _SEPARATORS and len(normalized) > 1:
            fcat = _find_category(normalized)
            if fcat:
                from_unit = normalized
                break

    if not from_unit or not to_unit:
        return None
    return value, from_unit, to_unit


def try_unit_conversion_fast_path(query: str) -> str | None:
    if not _CONVERT_RE.search(query):
        return None

    parsed = _extract_conversion(query)
    if parsed is None:
        return (
            "No pude identificar la conversión. "
            "Ej: 'convertir 10 km a millas' o 'cuántos grados celsius son 100 fahrenheit'."
        )

    value, from_unit, to_unit = parsed
    result = _convert_value(value, from_unit, to_unit)
    if result is None:
        return (
            f"No sé convertir '{from_unit}' a '{to_unit}'. "
            "Unidades soportadas: longitud (km,m,cm,mi,ft,in), peso (kg,lb,oz), "
            "temperatura (celsius,fahrenheit,kelvin), volumen (l,gal), tiempo (h,min,s)."
        )
    return result
