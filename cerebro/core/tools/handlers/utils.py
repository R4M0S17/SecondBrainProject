from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from loguru import logger


def get_current_datetime() -> str:
    return datetime.now(UTC).isoformat()


def create_note(title: str, content: str, notes_dir: str) -> str:
    notes_path = Path(notes_dir)
    notes_path.mkdir(parents=True, exist_ok=True)
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title).strip()
    filename = f"{safe_title}.md" if safe_title else "untitled.md"
    note_path = notes_path / filename
    note_path.write_text(f"# {title}\n\n{content}", encoding="utf-8")
    logger.info("create_note: {}", note_path)
    return str(note_path)
