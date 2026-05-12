"""Tests for Module A5 — Tool Governance."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from core.agents.state_store import AgentProfile
from core.tools.audit import AuditLogger
from core.tools.policy import PolicyEngine
from core.tools.registry import AuditLevel, ToolDefinition, ToolRegistry, ToolScope

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_profile(authorized_tools: list[str]) -> AgentProfile:
    return AgentProfile(
        id="test-agent",
        name="TestAgent",
        domain_tags=["test"],
        authorized_tools=authorized_tools,
        preferences={},
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
    )


def _make_tool(name: str, requires_confirmation: bool = False) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=f"Tool {name}",
        handler=lambda: None,
        required_permission=f"tools.{name}",
        requires_confirmation=requires_confirmation,
        scope=ToolScope.LOCAL,
        audit_level=AuditLevel.METADATA,
    )


def _make_registry(*names: str) -> ToolRegistry:
    reg = ToolRegistry()
    for name in names:
        reg.register(_make_tool(name))
    return reg


# ---------------------------------------------------------------------------
# ToolRegistry
# ---------------------------------------------------------------------------


def test_registry_get_known_tool():
    reg = _make_registry("read_file")
    tool = reg.get("read_file")
    assert tool.name == "read_file"


def test_registry_get_unknown_tool_raises():
    reg = _make_registry("read_file")
    with pytest.raises(KeyError):
        reg.get("nonexistent")


def test_registry_list_for_agent_filters_by_authorized():
    reg = _make_registry("read_file", "write_file", "execute_python")
    agent = _make_profile(["read_file", "execute_python"])
    tools = reg.list_for_agent(agent)
    names = {t.name for t in tools}
    assert names == {"read_file", "execute_python"}


def test_registry_is_authorized_true():
    reg = _make_registry("read_file")
    agent = _make_profile(["read_file"])
    assert reg.is_authorized("read_file", agent) is True


def test_registry_is_authorized_false_not_in_profile():
    reg = _make_registry("read_file", "write_file")
    agent = _make_profile(["read_file"])
    assert reg.is_authorized("write_file", agent) is False


def test_registry_is_authorized_false_not_registered():
    reg = _make_registry("read_file")
    agent = _make_profile(["write_file"])
    assert reg.is_authorized("write_file", agent) is False


# ---------------------------------------------------------------------------
# PolicyEngine — rejects tool not in agent's authorized_tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_policy_rejects_unauthorized_tool():
    reg = _make_registry("read_file", "write_file")
    engine = PolicyEngine(reg, authorized_write_paths=["/tmp"], watched_paths=["/tmp"])
    agent = _make_profile(["read_file"])
    tool = reg.get("write_file")

    result = await engine.validate_call(tool, {"path": "/tmp/x.txt", "content": "hi"}, agent)

    assert result.approved is False
    assert "not authorized" in (result.reason or "").lower()


# ---------------------------------------------------------------------------
# PolicyEngine — write_file outside authorized_write_paths → rejected
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_policy_rejects_write_outside_authorized_paths(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    other = tmp_path / "other"
    other.mkdir()

    reg = _make_registry("write_file")
    engine = PolicyEngine(
        reg,
        authorized_write_paths=[str(allowed)],
        watched_paths=[str(tmp_path)],
    )
    agent = _make_profile(["write_file"])
    tool = reg.get("write_file")

    result = await engine.validate_call(
        tool, {"path": str(other / "evil.txt"), "content": "hack"}, agent
    )

    assert result.approved is False
    assert "authorized_write_paths" in (result.reason or "")


@pytest.mark.asyncio
async def test_policy_approves_write_inside_authorized_paths(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()

    reg = _make_registry("write_file")
    engine = PolicyEngine(
        reg,
        authorized_write_paths=[str(allowed)],
        watched_paths=[str(tmp_path)],
    )
    agent = _make_profile(["write_file"])
    tool = reg.get("write_file")

    result = await engine.validate_call(
        tool, {"path": str(allowed / "note.txt"), "content": "safe"}, agent
    )

    assert result.approved is True
    assert "content" not in result.sanitized_args  # content is stripped from sanitized_args


# ---------------------------------------------------------------------------
# PolicyEngine — execute_python code is sanitized in audit args
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_policy_sanitizes_execute_python_code():
    reg = _make_registry("execute_python")
    engine = PolicyEngine(reg, authorized_write_paths=[], watched_paths=[])
    agent = _make_profile(["execute_python"])
    tool = reg.get("execute_python")

    code = "import math; print(math.pi)"
    result = await engine.validate_call(tool, {"code": code}, agent)

    assert result.approved is True
    assert result.sanitized_args.get("code") != code
    assert "chars" in result.sanitized_args.get("code", "")


# ---------------------------------------------------------------------------
# PolicyEngine — requires_user_confirmation propagated correctly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_policy_propagates_confirmation_flag(tmp_path):
    reg = ToolRegistry()
    reg.register(
        ToolDefinition(
            name="write_file",
            description="Write a file",
            handler=lambda: None,
            required_permission="tools.write_file",
            requires_confirmation=True,
            scope=ToolScope.LOCAL,
            audit_level=AuditLevel.METADATA,
        )
    )
    engine = PolicyEngine(
        reg,
        authorized_write_paths=[str(tmp_path)],
        watched_paths=[str(tmp_path)],
    )
    agent = _make_profile(["write_file"])
    tool = reg.get("write_file")

    result = await engine.validate_call(
        tool, {"path": str(tmp_path / "f.txt"), "content": "x"}, agent
    )

    assert result.approved is True
    assert result.requires_user_confirmation is True


# ---------------------------------------------------------------------------
# AuditLogger — does not write document content
# ---------------------------------------------------------------------------


def test_audit_logger_writes_record(tmp_path):
    audit = AuditLogger(str(tmp_path / "audit"))
    audit.log_tool_call(
        agent_id="agent-1",
        tool="read_file",
        args_sanitized={"path": "/tmp/doc.txt"},
        result_summary="read 1234 bytes",
        approved=True,
        timestamp=datetime.now(UTC),
    )
    logs = list((tmp_path / "audit").glob("audit-*.jsonl"))
    assert len(logs) == 1
    record = json.loads(logs[0].read_text().strip())
    assert record["tool"] == "read_file"
    assert record["approved"] is True
    assert record["agent_id"] == "agent-1"


def test_audit_logger_does_not_write_document_content(tmp_path):
    audit = AuditLogger(str(tmp_path / "audit"))
    audit.log_tool_call(
        agent_id="agent-1",
        tool="read_file",
        args_sanitized={"path": "/tmp/doc.txt"},
        result_summary="read 500 bytes",
        approved=True,
        timestamp=datetime.now(UTC),
    )
    log_content = (tmp_path / "audit").glob("audit-*.jsonl")
    raw = next(log_content).read_text()
    assert "content" not in raw
    assert "500 bytes" in raw  # summary is fine, but not actual content


def test_audit_logger_monthly_rotation(tmp_path):
    audit = AuditLogger(str(tmp_path / "audit"))
    ts = datetime.now(UTC)
    audit.log_tool_call("a", "read_file", {}, "ok", True, ts)
    month = ts.strftime("%Y-%m")
    expected = tmp_path / "audit" / f"audit-{month}.jsonl"
    assert expected.exists()


# ---------------------------------------------------------------------------
# Phase 4 — PolicyEngine for new Phase 1-3 tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_policy_rejects_run_script_outside_authorized_paths(tmp_path):
    allowed = tmp_path / "scripts"
    allowed.mkdir()
    other = tmp_path / "other"
    other.mkdir()

    reg = _make_registry("run_script")
    engine = PolicyEngine(
        reg,
        authorized_write_paths=[str(allowed)],
        watched_paths=[str(tmp_path)],
    )
    agent = _make_profile(["run_script"])
    tool = reg.get("run_script")

    result = await engine.validate_call(tool, {"filepath": str(other / "evil.py")}, agent)

    assert result.approved is False
    assert "authorized_write_paths" in (result.reason or "")


@pytest.mark.asyncio
async def test_policy_rejects_delete_file_outside_authorized_paths(tmp_path):
    allowed = tmp_path / "files"
    allowed.mkdir()
    other = tmp_path / "other"
    other.mkdir()

    reg = _make_registry("delete_file")
    engine = PolicyEngine(
        reg,
        authorized_write_paths=[str(allowed)],
        watched_paths=[str(tmp_path)],
    )
    agent = _make_profile(["delete_file"])
    tool = reg.get("delete_file")

    result = await engine.validate_call(tool, {"path": str(other / "important.txt")}, agent)

    assert result.approved is False
    assert "authorized_write_paths" in (result.reason or "")


@pytest.mark.asyncio
async def test_policy_sanitizes_create_python_file_code():
    reg = _make_registry("create_python_file")
    engine = PolicyEngine(reg, authorized_write_paths=[], watched_paths=[])
    agent = _make_profile(["create_python_file"])
    tool = reg.get("create_python_file")

    code = "import os\nos.system('rm -rf /')"
    result = await engine.validate_call(tool, {"filename": "script.py", "code": code}, agent)

    assert result.approved is True
    assert result.sanitized_args.get("code") != code
    assert "chars" in result.sanitized_args.get("code", "")
