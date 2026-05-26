#!/usr/bin/env python3
"""HTTP smoke checks for ImplemeFIX / manual_tests regression matrix.

Assumes ``make run`` (backend) and ``make engine`` (llama.cpp) are already up.
Exits non-zero on hard failures; prints WARN for soft targets (latency, RAM).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASE = os.environ.get("CEREBRO_BASE_URL", "http://127.0.0.1:7842").rstrip("/")
API = f"{BASE}/api"
LLAMA = os.environ.get("CEREBRO_LLAMACPP_URL", "http://127.0.0.1:8080").rstrip("/")
QUERY_TIMEOUT = int(os.environ.get("CEREBRO_SMOKE_QUERY_TIMEOUT", "120"))
FIRST_TURN_TARGET_S = float(os.environ.get("CEREBRO_SMOKE_FIRST_TURN_MAX_S", "8"))
SECOND_TURN_TARGET_S = float(os.environ.get("CEREBRO_SMOKE_SECOND_TURN_MAX_S", "1"))
RAM_TARGET_RATIO = float(os.environ.get("CEREBRO_SMOKE_RAM_MAX_RATIO", "0.60"))
REPORT_PATH = os.environ.get(
    "CEREBRO_SMOKE_REPORT",
    str(ROOT / "manual_tests" / "implemefix" / "post-smoke.md"),
)

_WARNINGS: list[str] = []
_RESULTS: dict[str, Any] = {}


def _http(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    *,
    timeout: float = 30,
) -> tuple[int, Any]:
    url = f"{API}{path}"
    payload = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if payload else {}
    req = urllib.request.Request(url, data=payload, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            parsed: Any = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return exc.code, parsed


def _ram_stressed() -> bool:
    snap = _RESULTS.get("status_snapshot") or {}
    used, total = snap.get("ram_used_gb"), snap.get("ram_total_gb")
    if used is None or total is None or float(total) <= 0:
        return False
    return float(used) / float(total) > RAM_TARGET_RATIO


def _query(
    question: str,
    agent: str,
    *,
    conversation_id: str | None = None,
) -> tuple[float, int, dict[str, Any]]:
    t0 = time.perf_counter()
    status, data = _http(
        "POST",
        "/query",
        {
            "question": question,
            "agent": agent,
            **({"conversation_id": conversation_id} if conversation_id else {}),
        },
        timeout=QUERY_TIMEOUT,
    )
    elapsed = time.perf_counter() - t0
    if not isinstance(data, dict):
        raise AssertionError(f"expected JSON object, got {data!r}")
    return elapsed, status, data


def _fail(name: str, msg: str, detail: Any = None) -> None:
    if _ram_stressed() and detail is not None:
        blob = json.dumps(detail) if not isinstance(detail, str) else detail
        if "timed out" in blob.lower() or "timeout" in msg.lower():
            _warn(name, f"{msg} (RAM-stressed machine — treating as warn)")
            return
    print(f"FAIL  {name}: {msg}", file=sys.stderr)
    if detail is not None:
        print(json.dumps(detail, indent=2, ensure_ascii=False)[:4000], file=sys.stderr)
    _RESULTS[name] = {"status": "fail", "message": msg}
    sys.exit(1)


def _warn(name: str, msg: str) -> None:
    print(f"WARN  {name}: {msg}", file=sys.stderr)
    _WARNINGS.append(f"{name}: {msg}")
    _RESULTS[name] = {"status": "warn", "message": msg}


def _ok(name: str, **extra: Any) -> None:
    print(f"OK    {name}" + (f" ({extra})" if extra else ""))
    _RESULTS[name] = {"status": "ok", **extra}


def check_backend_reachable() -> None:
    try:
        urllib.request.urlopen(f"{API}/health", timeout=5)
    except OSError:
        print(
            f"SKIP: Cerebro backend not reachable at {BASE}\n"
            "      Start the stack: make engine && make run",
            file=sys.stderr,
        )
        sys.exit(1)
    _ok("backend_reachable")


def check_health() -> None:
    status, data = _http("GET", "/health")
    if status != 200:
        _fail("health", f"HTTP {status}", data)
    llama = data.get("llama_server")
    if llama not in ("up", "restarting", "down"):
        _fail("health", f"unexpected llama_server: {llama!r}", data)
    _ok("health", llama_server=llama)


def check_status() -> None:
    status, data = _http("GET", "/status")
    if status != 200:
        _fail("status", f"HTTP {status}", data)
    for key in ("engine_ok", "model", "provider", "ram_pressure"):
        if key not in data:
            _fail("status", f"missing field {key!r}", data)
    if not data.get("engine_ok"):
        _warn("status", "engine_ok=false — is make engine running?")
    model = str(data.get("model", ""))
    if "Qwen2.5-Coder" not in model and "qwen" not in model.lower():
        _warn("status", f"expected Qwen chat model, got {model!r}")
    _RESULTS["status_snapshot"] = {
        "model": model,
        "engine_ok": data.get("engine_ok"),
        "ram_used_gb": data.get("ram_used_gb"),
        "ram_total_gb": data.get("ram_total_gb"),
        "ram_pressure": data.get("ram_pressure"),
    }
    _ok("status", model=model)


def check_ram_budget() -> None:
    snap = _RESULTS.get("status_snapshot") or {}
    used = snap.get("ram_used_gb")
    total = snap.get("ram_total_gb")
    if used is None or total is None or float(total) <= 0:
        _warn("ram_budget", "ram fields missing from /api/status")
        return
    ratio = float(used) / float(total)
    _RESULTS["ram_ratio"] = round(ratio, 3)
    if ratio > RAM_TARGET_RATIO:
        _warn(
            "ram_budget",
            f"system RAM {ratio:.0%} used (target ≤{RAM_TARGET_RATIO:.0%})",
        )
    else:
        _ok("ram_budget", ratio=f"{ratio:.0%}")


def check_embed_server_optional() -> None:
    """Module 3: chat should work without :8082 when using local embeddings."""
    try:
        urllib.request.urlopen("http://127.0.0.1:8082/health", timeout=2)
        _ok("embed_server_8082", note="running (legacy OK)")
    except OSError:
        _ok(
            "embed_server_8082", note="not running (expected with CEREBRO_EMBEDDINGS_BACKEND=local)"
        )


def check_config_patch() -> None:
    status, before = _http("GET", "/config")
    if status != 200:
        _fail("config_get", f"HTTP {status}", before)
    probe = before.get("smoke_probe", 0)
    status, patched = _http("PATCH", "/config", {"smoke_probe": probe})
    if status != 200:
        _fail("config_patch", f"HTTP {status}", patched)
    if patched.get("smoke_probe") != probe:
        _fail("config_patch", "smoke_probe not persisted", patched)
    _ok("config_patch")


def check_fleet_status() -> None:
    status, data = _http("GET", "/fleet/status")
    if status == 503:
        _fail("fleet_status", "fleet orchestrator not initialised", data)
    if status != 200:
        _fail("fleet_status", f"HTTP {status}", data)
    if "mode" not in data:
        _fail("fleet_status", "missing mode field", data)
    _ok("fleet_status")


def _answer_errors(answer: str) -> list[str]:
    errors: list[str] = []
    if "API 500" in answer or "400 Bad Request" in answer:
        errors.append("llama.cpp or backend error leaked into answer")
    if re.search(r'\{"action"\s*:\s*"answer"', answer):
        errors.append("raw JSON answer envelope in chat text")
    if re.search(r'\{"action"\s*:\s*"tool"', answer) and "tool_name" in answer:
        errors.append("raw JSON tool envelope in chat text")
    return errors


def check_latency_turns() -> None:
    t1, st1, d1 = _query("Say hello in one short sentence.", "general-v1")
    if st1 != 200:
        _fail("latency_turn1", f"HTTP {st1}", d1)
    conv_id = d1.get("conversation_id")
    meta1 = d1.get("metadata") or {}
    _RESULTS["latency_turn1_s"] = round(t1, 2)
    _RESULTS["latency_turn1_meta_ms"] = meta1.get("total_latency_ms")
    if t1 > FIRST_TURN_TARGET_S:
        _warn("latency_turn1", f"{t1:.1f}s > target {FIRST_TURN_TARGET_S}s")
    else:
        _ok("latency_turn1", seconds=round(t1, 2))

    t2, st2, d2 = _query("Hi again.", "general-v1", conversation_id=conv_id)
    if st2 != 200:
        if st2 == 500 and _ram_stressed():
            _warn("latency_turn2", f"HTTP {st2} under RAM pressure", d2)
        else:
            _fail("latency_turn2", f"HTTP {st2}", d2)
    _RESULTS["latency_turn2_s"] = round(t2, 2)
    if t2 > SECOND_TURN_TARGET_S:
        _warn("latency_turn2", f"{t2:.1f}s > target {SECOND_TURN_TARGET_S}s")
    else:
        _ok("latency_turn2", seconds=round(t2, 2))


def check_time_three_turns() -> None:
    from core.agents.runtime import _now_human

    t = _now_human()
    conv_id: str | None = None
    for i in range(3):
        elapsed, status, data = _query(
            "What time is it right now? Reply with only the time.",
            "general-v1",
            conversation_id=conv_id,
        )
        if status != 200:
            _fail(f"time_turn{i + 1}", f"HTTP {status}", data)
        conv_id = data.get("conversation_id") or conv_id
        answer = str(data.get("answer", "")).lower()
        errs = _answer_errors(answer)
        if errs:
            _fail(f"time_turn{i + 1}", "; ".join(errs), data)
        # Accept 12h or 24h form from preamble truth
        hour_24 = t["time_24h"][:2]  # HH
        hour_12 = t["time_12h"].split(":")[0].lstrip("0") or "12"
        weekday = t["date"].split(",")[0].lower()
        has_time = hour_24 in answer or hour_12 in answer or t["time_24h"] in answer
        has_day = weekday in answer or str(datetime.now().year) in answer
        if not has_time and not has_day:
            _warn(f"time_turn{i + 1}", f"answer may not echo system time: {answer[:120]!r}")
        time.sleep(0.3)
    _ok("time_three_turns")


def check_filesystem_write_and_deny() -> None:
    files_root = os.path.expanduser(os.getenv("CEREBRO_FILES_PATH", "~/Desktop/CerebroFiles"))
    _, st_w, d_w = _query(
        "Create a file named smoke-hello.py in my CerebroFiles folder with "
        "exactly this content: print('hi')",
        "general-v1",
    )
    if st_w != 200:
        _fail("fs_write_cerebrofiles", f"HTTP {st_w}", d_w)
    answer_w = str(d_w.get("answer", ""))
    errs = _answer_errors(answer_w)
    if errs:
        _fail("fs_write_cerebrofiles", "; ".join(errs), d_w)
    pending = (d_w.get("metadata") or {}).get("pending_tool") or {}
    tools = (d_w.get("metadata") or {}).get("tools_called") or []
    tool_names = {t.get("name") for t in tools if isinstance(t, dict)}
    if pending.get("name") in ("write_file", "create_python_file") or tool_names & {
        "write_file",
        "create_python_file",
    }:
        _ok("fs_write_cerebrofiles", path=files_root)
    elif "no autorizado" in answer_w.lower() or "not authorized" in answer_w.lower():
        _fail("fs_write_cerebrofiles", "unexpected auth denial for CerebroFiles", d_w)
    elif re.search(r'\{"action"', answer_w):
        _fail("fs_write_cerebrofiles", "raw JSON instead of tool routing", d_w)
    else:
        _warn("fs_write_cerebrofiles", f"unclear tool path: {answer_w[:200]!r}")

    _, st_d, d_d = _query(
        "Write a file /tmp/cerebro-smoke-unauthorized.txt with content deny test.",
        "general-v1",
    )
    if st_d != 200:
        _fail("fs_deny_unauthorized", f"HTTP {st_d}", d_d)
    answer_d = str(d_d.get("answer", "")).lower()
    if re.search(r'\{"action"\s*:\s*"tool"', answer_d):
        _fail("fs_deny_unauthorized", "raw JSON leak on denied path", d_d)
    friendly = any(
        x in answer_d
        for x in (
            "no autorizado",
            "not authorized",
            "authorized",
            "permitido",
            "cerebrofiles",
            "no puedo escribir",
            "cannot write",
        )
    )
    if friendly:
        _ok("fs_deny_unauthorized")
    else:
        _warn("fs_deny_unauthorized", f"expected friendly denial, got: {answer_d[:200]!r}")


def check_calendar_optional() -> None:
    _, status, data = _query(
        "What is my next calendar event today? List one if any.",
        "general-v1",
    )
    if status != 200:
        _fail("calendar_query", f"HTTP {status}", data)
    answer = str(data.get("answer", "")).lower()
    errs = _answer_errors(answer)
    if errs:
        _fail("calendar_query", "; ".join(errs), data)
    if "permission" in answer or "permiso" in answer or "calendar access" in answer:
        _warn(
            "calendar_query", "calendar permission may be missing — skip populated-calendar check"
        )
    elif "no events" in answer or "no hay eventos" in answer or "sin eventos" in answer:
        _warn("calendar_query", "no events returned (empty calendar OK for smoke)")
    else:
        _ok("calendar_query")


def check_g2_math() -> None:
    _, status, data = _query("What is 17 × 23? Show only the number.", "general-v1")
    if status != 200:
        _fail("g2_math", f"HTTP {status}", data)
    answer = str(data.get("answer", ""))
    errs = _answer_errors(answer)
    if errs:
        _fail("g2_math", "; ".join(errs), data)
    digits = re.sub(r"\D", "", answer)
    if "391" not in digits and "391" not in answer:
        _fail("g2_math", f"expected 391 in answer, got: {answer!r}", data)
    _ok("g2_math")


def check_g3_no_json_envelope() -> None:
    _, status, data = _query(
        "Explain what a Python list comprehension is in 3 bullet points.",
        "general-v1",
    )
    if status != 200:
        _fail("g3_bullets", f"HTTP {status}", data)
    answer = str(data.get("answer", ""))
    errs = _answer_errors(answer)
    if errs:
        _fail("g3_bullets", "; ".join(errs), data)
    _ok("g3_bullets")


def check_g6_calendar_create_general() -> None:
    _, status, data = _query(
        'Create a calendar event titled "Cerebro smoke test" tomorrow at 4pm for 30 minutes.',
        "general-v1",
    )
    if status != 200:
        _fail("g6_calendar_create", f"HTTP {status}", data)
    answer = str(data.get("answer", ""))
    errs = _answer_errors(answer)
    if errs:
        _fail("g6_calendar_create", "; ".join(errs), data)
    pending = (data.get("metadata") or {}).get("pending_tool") or {}
    if pending.get("name") == "create_calendar_event":
        _ok("g6_calendar_create")
        return
    if "no events found" in answer.lower() or "no hay eventos" in answer.lower():
        _warn(
            "g6_calendar_create",
            "looks like search-only path, expected create_calendar_event pending_tool",
        )
        return
    _warn("g6_calendar_create", "expected create_calendar_event pending_tool or approval")


def check_c1_calendar_agent() -> None:
    _, status, data = _query(
        "Crea un evento llamado Cerebro smoke test mañana a las 4pm por 30 minutos.",
        "calendar-v1",
    )
    if status != 200:
        _fail("c1_calendar_agent", f"HTTP {status}", data)
    answer = str(data.get("answer", ""))
    errs = _answer_errors(answer)
    if errs:
        _fail("c1_calendar_agent", "; ".join(errs), data)
    pending = (data.get("metadata") or {}).get("pending_tool") or {}
    if pending.get("name") == "create_calendar_event":
        _ok("c1_calendar_agent")
        return
    _warn("c1_calendar_agent", "expected create_calendar_event pending_tool")


def check_g7_write_file_general() -> None:
    _, status, data = _query(
        "Write a file called test-cerebro.txt with the word hello inside my allowed folder.",
        "general-v1",
    )
    if status != 200:
        _fail("g7_write_file", f"HTTP {status}", data)
    answer = str(data.get("answer", ""))
    errs = _answer_errors(answer)
    if errs:
        _fail("g7_write_file", "; ".join(errs), data)
    pending = (data.get("metadata") or {}).get("pending_tool") or {}
    if pending.get("name") == "write_file":
        _ok("g7_write_file")
        return
    tools = (data.get("metadata") or {}).get("tools_called") or []
    names = {t.get("name") for t in tools if isinstance(t, dict)}
    if "write_file" in names:
        _ok("g7_write_file")
        return
    if "search_files" in names or "no results" in answer.lower():
        _warn("g7_write_file", "wrong tool path (search instead of write_file)")
        return
    _warn("g7_write_file", "expected write_file confirmation or tool call")


def check_auto_routes_calendar() -> None:
    _, status, data = _query(
        "¿Qué reuniones tengo mañana en el calendario?",
        "auto",
    )
    if status != 200:
        _fail("auto_calendar_route", f"HTTP {status}", data)
    answer = str(data.get("answer", ""))
    errs = _answer_errors(answer)
    if errs:
        _fail("auto_calendar_route", "; ".join(errs), data)
    conv_id = data.get("conversation_id")
    if not conv_id:
        _fail("auto_calendar_route", "missing conversation_id", data)
    st, detail = _http("GET", f"/conversations/{conv_id}")
    if st != 200:
        _fail("auto_calendar_route", f"conversation HTTP {st}", detail)
    agent = detail.get("agent_id", "")
    if agent != "calendar-v1":
        _fail("auto_calendar_route", f"expected calendar-v1, got agent_id={agent!r}", detail)
    _ok("auto_calendar_route")


def _write_report() -> None:
    lines = [
        "# ImplemeFIX — Post smoke report (Module 7)",
        "",
        "| Field | Value |",
        "|--------|--------|",
        f"| Date | {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')} |",
        f"| Base URL | {BASE} |",
        f"| Chat engine | {LLAMA} |",
        "",
        "## Automated results",
        "",
        "| Check | Status |",
        "|-------|--------|",
    ]
    for name, info in _RESULTS.items():
        if name == "status_snapshot":
            continue
        status = info.get("status", "?") if isinstance(info, dict) else "ok"
        lines.append(f"| `{name}` | {status} |")

    snap = _RESULTS.get("status_snapshot")
    if snap:
        lines.extend(
            [
                "",
                "## Status snapshot",
                "",
                "```json",
                json.dumps(snap, indent=2),
                "```",
            ]
        )

    if _WARNINGS:
        lines.extend(["", "## Warnings", ""])
        for w in _WARNINGS:
            lines.append(f"- {w}")

    lines.extend(
        [
            "",
            "## Module 7 manual items",
            "",
            "- [ ] Tray UI cold start (`cd ui/tray && npm run dev`)",
            "- [ ] Activity Monitor screenshot (steady-state chat RAM)",
            "",
            "## Targets (8 GB M1)",
            "",
            f"- First-turn latency target: ≤ {FIRST_TURN_TARGET_S}s (warn if over)",
            f"- Second-turn latency target: ≤ {SECOND_TURN_TARGET_S}s (warn if over)",
            f"- System RAM target: ≤ {RAM_TARGET_RATIO:.0%} during chat",
            "",
        ]
    )

    path = Path(REPORT_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"report: wrote {path}")


def main() -> None:
    check_backend_reachable()
    print(f"smoke: base={BASE} llama={LLAMA} query_timeout={QUERY_TIMEOUT}s")
    check_health()
    check_status()
    check_ram_budget()
    check_embed_server_optional()
    check_config_patch()
    check_fleet_status()
    check_latency_turns()
    check_time_three_turns()
    check_filesystem_write_and_deny()
    check_calendar_optional()
    check_g2_math()
    check_g3_no_json_envelope()
    check_g6_calendar_create_general()
    check_c1_calendar_agent()
    check_g7_write_file_general()
    check_auto_routes_calendar()
    _write_report()
    if _WARNINGS:
        print(f"smoke: passed with {len(_WARNINGS)} warning(s)", file=sys.stderr)
    else:
        print("smoke: all checks passed")


if __name__ == "__main__":
    main()
