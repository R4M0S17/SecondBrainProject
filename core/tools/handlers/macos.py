"""macOS tool handlers — thin wrappers over integrations.macos_apps."""

from __future__ import annotations

from integrations.macos_apps import (
    create_note,
    search_notes,
    send_notification,
    spotlight_search,
)

__all__ = ["spotlight_search", "create_note", "search_notes", "send_notification"]
