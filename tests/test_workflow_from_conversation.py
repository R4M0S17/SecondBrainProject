from __future__ import annotations

from core.automation.from_conversation import (
    infer_recipe_key_from_tools,
    workflow_to_export_dict,
)


def test_infer_recipe_key_write_file():
    tools = [{"name": "write_file", "approved": True, "result_summary": "ok"}]
    assert infer_recipe_key_from_tools(tools) == "calendar_to_file"


def test_infer_recipe_key_search_files():
    tools = [{"name": "search_files", "approved": True, "result_summary": "3 files"}]
    assert infer_recipe_key_from_tools(tools) == "search_pdfs_desktop"


def test_infer_recipe_key_skips_failed_tools():
    tools = [
        {"name": "write_file", "approved": True, "result_summary": "Error: denied"},
        {"name": "search_files", "approved": True, "result_summary": "found"},
    ]
    assert infer_recipe_key_from_tools(tools) == "search_pdfs_desktop"


def test_infer_recipe_key_none():
    assert infer_recipe_key_from_tools([]) is None
    assert infer_recipe_key_from_tools([{"name": "web_search", "result_summary": "ok"}]) is None


def test_workflow_to_export_dict():
    wf = {
        "name": "Demo",
        "description": "d",
        "workflow_type": "recipe",
        "applescript": "",
        "recipe_key": "add_reminder",
        "parameters": [{"name": "title", "type": "string"}],
        "steps": [{"order": 1, "action": "Add reminder"}],
        "tags": ["x"],
    }
    exported = workflow_to_export_dict(wf)
    assert exported["version"] == 1
    assert exported["recipe_key"] == "add_reminder"
    assert exported["steps"][0]["action"] == "Add reminder"
