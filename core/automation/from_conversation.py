"""Create recipe workflows from saved conversation turns."""

from __future__ import annotations

from typing import Any

from core.automation.recipes import RECIPE_TEMPLATES, get_template

_RECIPE_TOOL_MAP: dict[str, str] = {
    "add_reminder": "add_reminder",
    "create_calendar_event": "add_reminder",
    "search_files": "search_pdfs_desktop",
    "write_file": "calendar_to_file",
}


def _is_successful_tool(tool: dict[str, Any]) -> bool:
    if tool.get("approved") is False:
        return False
    result = (tool.get("result_summary") or "").strip().lower()
    return not result.startswith("error")


def infer_recipe_key_from_tools(tools_called: list[dict[str, Any]]) -> str | None:
    """Map successful tool calls to a built-in recipe key."""
    successful = [t for t in tools_called if _is_successful_tool(t)]
    names = {t.get("name", "") for t in successful}
    for tool_name, recipe_key in _RECIPE_TOOL_MAP.items():
        if tool_name in names:
            return recipe_key
    return None


def create_recipe_from_conversation(
    conv_store: Any,
    workflow_store: Any,
    conversation_id: str,
    turn_index: int,
    *,
    name: str | None = None,
) -> dict[str, Any]:
    """Persist a recipe workflow inferred from an assistant turn's tool metadata."""
    if workflow_store is None:
        raise RuntimeError("Workflow store not available")
    if conv_store is None:
        raise RuntimeError("Conversation store not available")

    record = conv_store.get(conversation_id)
    if record is None:
        raise KeyError(f"Conversation {conversation_id!r} not found")
    if turn_index < 0 or turn_index >= len(record.turns):
        raise IndexError("Turn index out of range")

    turn = record.turns[turn_index]
    if turn.role != "assistant":
        raise ValueError("Turn must be an assistant message")

    metadata = turn.metadata or {}
    tools_called = metadata.get("tools_called") or []
    if not tools_called:
        raise ValueError("No tools were called in this message")

    recipe_key = infer_recipe_key_from_tools(tools_called)
    if recipe_key is None:
        raise ValueError("No supported recipe could be inferred from tool calls")

    template = next((t for t in RECIPE_TEMPLATES if t["recipe_key"] == recipe_key), None)
    if template is None:
        template = get_template(f"recipe-{recipe_key}")
    if template is None:
        raise ValueError(f"Recipe template for {recipe_key!r} not found")

    wf_name = name or f"Receta: {template['name']}"
    tags = list(template.get("tags", [])) + ["from-chat"]
    wid = workflow_store.save(
        name=wf_name,
        applescript="",
        description=template["description"],
        parameters=template["parameters"],
        tags=tags,
        steps=template["steps"],
        workflow_type="recipe",
        recipe_key=recipe_key,
    )
    wf = workflow_store.get(wid)
    if wf is None:
        raise RuntimeError("Failed to load saved workflow")
    return wf


def workflow_to_export_dict(wf: dict[str, Any]) -> dict[str, Any]:
    """Serializable workflow payload for export/import."""
    return {
        "version": 1,
        "name": wf["name"],
        "description": wf.get("description", ""),
        "workflow_type": wf.get("workflow_type", "desktop"),
        "applescript": wf.get("applescript", ""),
        "recipe_key": wf.get("recipe_key"),
        "parameters": wf.get("parameters", []),
        "steps": wf.get("steps", []),
        "tags": wf.get("tags", []),
    }


def import_workflow_from_export(workflow_store: Any, data: dict[str, Any]) -> dict[str, Any]:
    """Create a workflow from an export JSON object."""
    if workflow_store is None:
        raise RuntimeError("Workflow store not available")

    name = (data.get("name") or "Imported workflow").strip()
    if not name:
        raise ValueError("Export missing name")

    wid = workflow_store.save(
        name=name,
        applescript=data.get("applescript", ""),
        description=data.get("description", ""),
        parameters=data.get("parameters", []),
        tags=list(data.get("tags", [])),
        steps=data.get("steps", []),
        workflow_type=data.get("workflow_type", "desktop"),
        recipe_key=data.get("recipe_key"),
    )
    wf = workflow_store.get(wid)
    if wf is None:
        raise RuntimeError("Failed to load imported workflow")
    return wf
