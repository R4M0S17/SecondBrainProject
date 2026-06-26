from __future__ import annotations

from core.tools.registry import ToolRegistry


def audit_confirmation_gates(registry: ToolRegistry) -> list[str]:
    STATE_CHANGING_TOOLS = {
        "write_file", "create_directory", "delete_file", "create_python_file",
        "execute_python", "run_script",
        "create_calendar_event", "add_reminder", "delete_reminder",
        "start_recording", "stop_recording", "run_workflow",
        "upload_file",
    }

    issues = []
    for tool_name in STATE_CHANGING_TOOLS:
        try:
            td = registry.get(tool_name)
            if not td.requires_confirmation:
                issues.append(f"UNPROTECTED: {tool_name} does not require confirmation")
        except KeyError:
            issues.append(f"MISSING: {tool_name} is not registered")
    return issues
