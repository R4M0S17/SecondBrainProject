from __future__ import annotations

import platform
import re
import subprocess
from datetime import datetime

import psutil

_SYSTEM_INFO_RE = {
    "ram": re.compile(
        r"\b(?:ram|memoria|memory|ram\s+usage|memoria\s+(?:ram|disponible|usada|libre)|"
        r"cu[áa]nta\s+ram|free\s+ram|memory\s+usage|memory\s+pressure)\b",
        re.IGNORECASE,
    ),
    "cpu": re.compile(
        r"\b(?:cpu|processor|procesador|n[úu]cleos|cpu\s+usage|cores|"
        r"carga\s+del\s+cpu|uso\s+del\s+cpu|cpu\s+load)\b",
        re.IGNORECASE,
    ),
    "disk": re.compile(
        r"\b(?:disk|disco|storage|almacenamiento|"
        r"espacio\s+(?:en\s+)?disco|disk\s+space|free\s+space)\b",
        re.IGNORECASE,
    ),
    "system": re.compile(
        r"\b(?:system\s+info|system\s+status|diagn[oó]stico|"
        r"informaci[oó]n\s+del\s+sistema|specs|hardware|"
        r"qu[eé]\s+(?:hardware|sistema|mac)\s+tengo|"
        r"what\s+(?:hardware|system|mac)\s+(?:do\s+)?i\s+have|"
        r"system\s+specs|machine\s+specs|device\s+info)\b",
        re.IGNORECASE,
    ),
    "uptime": re.compile(
        r"\b(?:uptime|tiempo\s+(?:de\s+)?(?:activo|encendido)|"
        r"cu[áa]nto\s+tiempo\s+llevo|how\s+long\s+(?:has\s+)?(?:the\s+)?system\s+(?:been\s+)?(?:up|running))\b",
        re.IGNORECASE,
    ),
}

_ALL_SYSTEM_RE = re.compile(
    r"\b(?:system\s+info|system\s+status|diagn[oó]stico|"
    r"recursos\s+del\s+sistema|system\s+resources|"
    r"c[oó]mo\s+est[aá]\s+(?:el\s+)?(?:sistema|mac)|"
    r"status\s+del\s+sistema|"
    r"qu[eé]\s+(?:tal\s+)?(?:va|est[aá])\s+(?:el\s+)?(?:sistema|mac))\b",
    re.IGNORECASE,
)


def _macos_version() -> str:
    try:
        ver = subprocess.run(
            ["sw_vers", "-productVersion"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if ver.returncode == 0:
            name = subprocess.run(
                ["sw_vers", "-productName"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            os_name = (name.stdout or "").strip() or "macOS"
            return f"{os_name} {ver.stdout.strip()}"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return platform.system() + " " + platform.release()


def _format_ram() -> str:
    mem = psutil.virtual_memory()
    total = mem.total / (1024**3)
    used = mem.used / (1024**3)
    avail = mem.available / (1024**3)
    pct = mem.percent
    return f"**RAM:** {used:.1f} GB / {total:.1f} GB ({pct:.0f}%) — " f"disponible: {avail:.1f} GB"


def _format_cpu() -> str:
    count = psutil.cpu_count(logical=True)
    physical = psutil.cpu_count(logical=False) or count
    pct = psutil.cpu_percent(interval=0.3)
    freq = psutil.cpu_freq()
    freq_str = f" @ {freq.current:.0f} MHz" if freq else ""
    return f"**CPU:** {physical} físicos / {count} lógicos — {pct:.0f}% uso{freq_str}"


def _format_disk() -> str:
    parts = []
    for part in psutil.disk_partitions():
        if (
            part.fstype
            and "apfs" in part.fstype.lower()
            or "hfs" in part.fstype.lower()
            or "ext4" in part.fstype.lower()
            or "ntfs" in part.fstype.lower()
        ):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                total = usage.total / (1024**3)
                used = usage.used / (1024**3)
                if total > 0:
                    parts.append(
                        f"  {part.mountpoint}: {used:.1f} / {total:.1f} GB ({usage.percent:.0f}%)"
                    )
            except PermissionError:
                pass
    disk_str = "\n".join(parts) if parts else "  (sin datos)"
    return f"**Disco:**\n{disk_str}"


def _format_uptime() -> str:
    boot = psutil.boot_time()
    delta = datetime.now() - datetime.fromtimestamp(boot)
    days = delta.days
    hours = delta.seconds // 3600
    mins = (delta.seconds % 3600) // 60
    return f"**Encendido:** {days}d {hours}h {mins}m"


def _format_system() -> str:
    uname = platform.uname()
    return (
        f"**Sistema:** {_macos_version()}\n"
        f"**Host:** {uname.node}\n"
        f"**Arquitectura:** {uname.machine}"
    )


def try_system_info_fast_path(query: str) -> str | None:
    q = query.lower()

    is_full = bool(_ALL_SYSTEM_RE.search(q))

    parts = []
    for key, regex in _SYSTEM_INFO_RE.items():
        if is_full or regex.search(q):
            if key == "ram":
                parts.append(_format_ram())
            elif key == "cpu":
                parts.append(_format_cpu())
            elif key == "disk":
                parts.append(_format_disk())
            elif key == "system":
                parts.append(_format_system())
            elif key == "uptime":
                parts.append(_format_uptime())

    if not parts:
        return None

    if is_full or len(parts) > 1:
        lines = ["**Diagnóstico del sistema**", "", *parts]
        return "\n".join(lines)
    return parts[0]
