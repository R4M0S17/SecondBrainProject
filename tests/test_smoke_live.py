"""Live smoke tests against a running Cerebro backend.

Requires ``make engine`` + ``make run`` (or equivalent) on localhost:7842.
Run with::

    pytest tests/test_smoke_live.py -v

Or via Makefile::

    make smoke  # now delegates here

All tests are marked ``@pytest.mark.live`` so they are excluded from
``make test-stable`` (which uses ``-m 'not live'``).
"""

from __future__ import annotations

import os
import re
import time

import pytest
import requests

BASE = os.environ.get("CEREBRO_BASE_URL", "http://127.0.0.1:7842").rstrip("/")
API = f"{BASE}/api"
LLAMA = os.environ.get("CEREBRO_LLAMACPP_URL", "http://127.0.0.1:8080").rstrip("/")
QUERY_TIMEOUT = int(os.environ.get("CEREBRO_SMOKE_QUERY_TIMEOUT", "120"))
RAM_TARGET_RATIO = float(os.environ.get("CEREBRO_SMOKE_RAM_MAX_RATIO", "0.60"))

pytestmark = pytest.mark.live


def _get(path: str) -> requests.Response:
    return requests.get(f"{API}{path}", timeout=5)


def _post(path: str, body: dict | None = None) -> requests.Response:
    return requests.post(f"{API}{path}", json=body, timeout=QUERY_TIMEOUT)


def _patch(path: str, body: dict) -> requests.Response:
    return requests.patch(f"{API}{path}", json=body, timeout=10)


def _query(
    question: str, agent: str, *, conversation_id: str | None = None
) -> tuple[float, requests.Response]:
    t0 = time.perf_counter()
    body: dict = {"question": question, "agent": agent}
    if conversation_id:
        body["conversation_id"] = conversation_id
    resp = _post("/query", body)
    elapsed = time.perf_counter() - t0
    return elapsed, resp


def _answer_errors(answer: str) -> list[str]:
    errors: list[str] = []
    if "API 500" in answer or "400 Bad Request" in answer:
        errors.append("llama.cpp or backend error leaked into answer")
    if re.search(r'\{"action"\s*:\s*"answer"', answer):
        errors.append("raw JSON answer envelope in chat text")
    if re.search(r'\{"action"\s*:\s*"tool"', answer):
        errors.append("raw JSON tool envelope in chat text")
    return errors


def _require_backend() -> None:
    """Skip all tests if backend is unreachable."""
    try:
        r = requests.get(f"{API}/health", timeout=3)
        r.raise_for_status()
    except (requests.ConnectionError, requests.Timeout) as exc:
        pytest.exit(
            f"Cerebro backend not reachable at {BASE} — start: make engine && make run\n{exc}"
        )


def pytest_sessionstart(session: pytest.Session) -> None:
    _require_backend()


# ── Health & status ────────────────────────────────────────────────────────


class TestHealth:
    def test_health_endpoint(self):
        r = _get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data.get("llama_server") in ("up", "restarting", "down")

    def test_status_endpoint(self):
        r = _get("/status")
        assert r.status_code == 200
        data = r.json()
        for key in ("engine_ok", "model", "provider", "ram_pressure"):
            assert key in data, f"missing field {key!r}"

    def test_ram_budget(self):
        r = _get("/status")
        data = r.json()
        used = data.get("ram_used_gb")
        total = data.get("ram_total_gb")
        if used and total and float(total) > 0:
            ratio = float(used) / float(total)
            assert (
                ratio <= RAM_TARGET_RATIO
            ), f"system RAM {ratio:.0%} used (target ≤{RAM_TARGET_RATIO:.0%})"

    def test_engine_activity_endpoint(self):
        r = _get("/engine/activity")
        assert r.status_code == 200
        assert r.json().get("engine_state") in ("active", "suspended", "unknown")

    def test_config_get_and_patch(self):
        r = _get("/config")
        assert r.status_code == 200
        before = r.json()
        probe = before.get("smoke_probe", 0)
        r2 = _patch("/config", {"smoke_probe": probe})
        assert r2.status_code == 200
        assert r2.json().get("smoke_probe") == probe


# ── Query latency & basic turns ────────────────────────────────────────────


class TestBasicQueries:
    @pytest.mark.slow
    def test_first_turn_latency(self):
        elapsed, resp = _query("Say hello in one short sentence.", "general-v1")
        assert resp.status_code == 200
        data = resp.json()
        errs = _answer_errors(str(data.get("answer", "")))
        assert not errs, "; ".join(errs)
        assert "conversation_id" in data
        # Warn if first turn > 8s (common on 8GB RAM)
        if elapsed > 8:
            pytest.skip(f"first turn {elapsed:.1f}s (slow machine — informational)")

    @pytest.mark.slow
    def test_conversation_turns(self):
        """Two turns sharing a conversation_id."""
        _, r1 = _query("Say hello in one short sentence.", "general-v1")
        conv_id = r1.json().get("conversation_id")
        assert conv_id, "no conversation_id on first turn"
        _, r2 = _query("Hi again.", "general-v1", conversation_id=conv_id)
        assert r2.status_code == 200


# ── Fast paths ─────────────────────────────────────────────────────────────


class TestFastPaths:
    def test_math(self):
        _, resp = _query("What is 17 × 23? Show only the number.", "general-v1")
        assert resp.status_code == 200
        answer = str(resp.json().get("answer", ""))
        errs = _answer_errors(answer)
        assert not errs, "; ".join(errs)
        assert "391" in answer, f"expected 391 in answer, got: {answer!r}"

    @pytest.mark.slow
    def test_calendar_query(self):
        _, resp = _query("What is my next calendar event today? List one if any.", "general-v1")
        assert resp.status_code == 200
        answer = str(resp.json().get("answer", "")).lower()
        errs = _answer_errors(answer)
        assert not errs, "; ".join(errs)
        # Calendar may not have permissions — we just check no crash

    def test_file_search(self):
        _, resp = _query("busca archivos .py", "general-v1")
        assert resp.status_code == 200
        answer = str(resp.json().get("answer", ""))
        errs = _answer_errors(answer)
        assert not errs, "; ".join(errs)


# ── Filesystem tools ───────────────────────────────────────────────────────


class TestFilesystem:
    def test_write_file_pending_approval(self):
        _, resp = _query(
            "Create a file named smoke-hello.py in my CerebroFiles folder "
            "with exactly this content: print('hi')",
            "general-v1",
        )
        assert resp.status_code == 200
        data = resp.json()
        answer = str(data.get("answer", ""))
        errs = _answer_errors(answer)
        assert not errs, "; ".join(errs)
        pending = (data.get("metadata") or {}).get("pending_tool") or {}
        tools = (data.get("metadata") or {}).get("tools_called") or []
        tool_names = {t.get("name") for t in tools if isinstance(t, dict)}
        has_write = pending.get("name") in ("write_file", "create_python_file") or tool_names & {
            "write_file",
            "create_python_file",
        }
        has_denial = "no autorizado" in answer.lower() or "not authorized" in answer.lower()
        assert (
            has_write or has_denial
        ), f"expected write_file tool or auth denial, got: {answer[:200]!r}"

    def test_unauthorized_path_denial(self):
        _, resp = _query(
            "Write a file /tmp/cerebro-smoke-unauthorized.txt with content deny test.",
            "general-v1",
        )
        assert resp.status_code == 200
        answer = str(resp.json().get("answer", "")).lower()
        errs = _answer_errors(answer)
        assert not errs, "; ".join(errs)
        assert any(
            x in answer
            for x in (
                "no autorizado",
                "not authorized",
                "authorized",
                "permitido",
                "cerebrofiles",
                "no puedo escribir",
                "cannot write",
            )
        ), f"expected friendly denial, got: {answer[:200]!r}"


# ── Agent routing ──────────────────────────────────────────────────────────


class TestAgentRouting:
    def test_auto_routes_calendar(self):
        _, resp = _query("¿Qué reuniones tengo mañana en el calendario?", "auto")
        assert resp.status_code == 200
        data = resp.json()
        errs = _answer_errors(str(data.get("answer", "")))
        assert not errs, "; ".join(errs)
        conv_id = data.get("conversation_id")
        assert conv_id, "missing conversation_id"
        r = _get(f"/conversations/{conv_id}")
        assert r.status_code == 200
        agent = r.json().get("agent_id", "")
        assert agent == "calendar-v1", f"expected calendar-v1, got agent_id={agent!r}"
