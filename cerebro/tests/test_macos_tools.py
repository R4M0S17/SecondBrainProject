"""Tests for Phase 3 — macOS App Integration tools."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from core.tools.registry import ToolRegistry, register_macos_tools
from integrations.macos_apps import (
    create_note,
    search_notes,
    send_notification,
    spotlight_search,
)

# ---------------------------------------------------------------------------
# spotlight_search
# ---------------------------------------------------------------------------


@patch("integrations.macos_apps.subprocess.run")
def test_spotlight_search_returns_formatted_results(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="/Users/test/notes.pdf\n/Users/test/report.pdf\n",
    )
    result = spotlight_search("quarterly report", max_results=5)
    assert "quarterly report" in result
    assert "notes.pdf" in result
    assert "report.pdf" in result
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args[0] == "mdfind"
    assert "-limit" in args
    assert "5" in args


@patch("integrations.macos_apps.subprocess.run")
def test_spotlight_search_no_results(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="")
    result = spotlight_search("xyznonexistent")
    assert "No Spotlight results" in result


@patch("integrations.macos_apps.subprocess.run")
def test_spotlight_search_kind_filter(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="/tmp/doc.pdf\n")
    spotlight_search("report", kind="pdf")
    args = mock_run.call_args[0][0]
    # kind filter passes a combined mdfind query with the kind predicate
    combined_query = " ".join(args)
    assert "kMDItemKind" in combined_query
    assert "report" in combined_query


# ---------------------------------------------------------------------------
# create_note
# ---------------------------------------------------------------------------


@patch("integrations.macos_apps.platform.system", return_value="Darwin")
@patch("integrations.macos_apps._run_jxa")
def test_create_note_success(mock_jxa, mock_platform):
    mock_jxa.return_value = (True, "ok")
    result = create_note("Meeting Notes", "Discussed Q2 plans", folder="Work")
    assert "Meeting Notes" in result
    assert "Work" in result
    mock_jxa.assert_called_once()
    script = mock_jxa.call_args[0][0]
    assert '"Meeting Notes"' in script
    assert '"Discussed Q2 plans"' in script
    assert '"Work"' in script


@patch("integrations.macos_apps.platform.system", return_value="Darwin")
@patch("integrations.macos_apps._run_jxa")
def test_create_note_failure_returns_error(mock_jxa, mock_platform):
    mock_jxa.return_value = (False, "Notes not authorized")
    result = create_note("Test", "body")
    assert "Error" in result
    assert "Notes not authorized" in result


@patch("integrations.macos_apps.platform.system", return_value="Linux")
def test_create_note_non_macos(mock_platform):
    result = create_note("Test", "body")
    assert "macOS" in result
    assert "Test" in result


# ---------------------------------------------------------------------------
# search_notes
# ---------------------------------------------------------------------------


@patch("integrations.macos_apps.platform.system", return_value="Darwin")
@patch("integrations.macos_apps._run_jxa")
def test_search_notes_returns_formatted_results(mock_jxa, mock_platform):
    import json

    mock_jxa.return_value = (
        True,
        json.dumps(
            [
                {"title": "Project Alpha", "snippet": "Key deliverables for Q2"},
                {"title": "Alpha Notes", "snippet": "Follow-up items"},
            ]
        ),
    )
    result = search_notes("alpha", max_results=5)
    assert "alpha" in result.lower()
    assert "Project Alpha" in result
    assert "Alpha Notes" in result
    assert "Key deliverables" in result


@patch("integrations.macos_apps.platform.system", return_value="Darwin")
@patch("integrations.macos_apps._run_jxa")
def test_search_notes_no_results(mock_jxa, mock_platform):
    import json

    mock_jxa.return_value = (True, json.dumps([]))
    result = search_notes("xyznotfound")
    assert "No notes found" in result


@patch("integrations.macos_apps.platform.system", return_value="Darwin")
@patch("integrations.macos_apps._run_jxa")
def test_search_notes_jxa_includes_lowercase_keyword(mock_jxa, mock_platform):
    import json

    mock_jxa.return_value = (True, json.dumps([]))
    search_notes("MyQuery")
    script = mock_jxa.call_args[0][0]
    # keyword should be lowercased before embedding in JXA
    assert '"myquery"' in script


# ---------------------------------------------------------------------------
# send_notification
# ---------------------------------------------------------------------------


@patch("integrations.macos_apps.platform.system", return_value="Darwin")
@patch("integrations.macos_apps._run_applescript")
def test_send_notification_success(mock_as, mock_platform):
    mock_as.return_value = (True, "")
    result = send_notification("Cerebro", "Task complete")
    assert "Notification sent" in result
    mock_as.assert_called_once()
    script = mock_as.call_args[0][0]
    assert "Task complete" in script
    assert "Cerebro" in script
    assert "display notification" in script


@patch("integrations.macos_apps.platform.system", return_value="Linux")
def test_send_notification_non_macos(mock_platform):
    result = send_notification("Title", "Body")
    assert "macOS" in result


@patch("integrations.macos_apps.platform.system", return_value="Darwin")
@patch("integrations.macos_apps._run_applescript")
def test_send_notification_failure_returns_error(mock_as, mock_platform):
    mock_as.return_value = (False, "permission denied")
    result = send_notification("Title", "Body")
    assert "Error" in result


# ---------------------------------------------------------------------------
# register_macos_tools — all 4 tools registered with correct metadata
# ---------------------------------------------------------------------------


def test_register_macos_tools_registers_all_four():
    registry = ToolRegistry()
    register_macos_tools(registry)
    registered = set(registry.definitions().keys())
    assert {"spotlight_search", "create_note", "search_notes", "send_notification"} <= registered


def test_macos_tools_confirmation_flags():
    registry = ToolRegistry()
    register_macos_tools(registry)
    for name in ("spotlight_search", "create_note", "search_notes", "send_notification"):
        assert registry.get(name).requires_confirmation is False


def test_macos_tools_permissions():
    registry = ToolRegistry()
    register_macos_tools(registry)
    assert registry.get("spotlight_search").required_permission == "tools.macos.search"
    assert registry.get("create_note").required_permission == "tools.macos.notes.write"
    assert registry.get("search_notes").required_permission == "tools.macos.notes.read"
    assert registry.get("send_notification").required_permission == "tools.macos.notify"
