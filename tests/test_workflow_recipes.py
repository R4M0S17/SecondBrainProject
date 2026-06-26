"""Tests for workflow recipe templates and handlers."""

from __future__ import annotations

import tempfile

import pytest

from core.automation.recipes import (
    RECIPE_TEMPLATES,
    get_template,
    install_template,
    list_templates,
    run_recipe,
)
from core.automation.workflow_store import WorkflowStore


class TestRecipeTemplates:
    def test_list_templates(self):
        templates = list_templates()
        assert len(templates) == len(RECIPE_TEMPLATES)
        assert templates[0]["recipe_key"]

    def test_get_template(self):
        t = get_template("recipe-reminder")
        assert t is not None
        assert t["recipe_key"] == "add_reminder"

    def test_get_template_missing(self):
        assert get_template("nope") is None


class TestRecipeInstall:
    @pytest.fixture
    def store(self):
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
            db_path = f.name
        store = WorkflowStore(db_path)
        yield store
        store.close()
        import os

        os.unlink(db_path)

    def test_install_template(self, store):
        wf = install_template(store, "recipe-search-pdfs-desktop")
        assert wf is not None
        assert wf["workflow_type"] == "recipe"
        assert wf["recipe_key"] == "search_pdfs_desktop"


class TestRecipeRun:
    def test_run_search_pdfs(self, monkeypatch):
        monkeypatch.setattr(
            "core.automation.recipes.search_files",
            lambda *a, **k: "found.pdf",
        )
        wf = {
            "parameters": [{"name": "max_results", "type": "number", "default": "5"}],
        }
        result = run_recipe("search_pdfs_desktop", wf, {"max_results": "3"})
        assert "found.pdf" in result

    def test_run_reminder_missing_title(self):
        wf = {"parameters": []}
        result = run_recipe("add_reminder", wf, {"when": "tomorrow"})
        assert result.startswith("Error")

    def test_run_unknown_recipe(self):
        result = run_recipe("unknown_key", {}, {})
        assert "desconocida" in result
