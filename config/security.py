"""Module 12 — Security utilities.

Canonical path-authorization check used by every file-access operation.
All modules must call validate_path() before reading or writing files;
they must never access paths outside watched_paths or authorized_write_paths.
"""

from __future__ import annotations

from pathlib import Path


def validate_path(path: str, watched_paths: list[str]) -> bool:
    """Return True if *path* resolves to within any directory in *watched_paths*.

    Symlinks and ``..`` components are resolved before comparison, so traversal
    escapes are blocked.  An empty *watched_paths* list always returns False —
    no path is authorized when the allowlist is empty.
    """
    if not watched_paths:
        return False
    try:
        resolved = Path(path).resolve()
    except (OSError, ValueError):
        return False
    for watched in watched_paths:
        try:
            resolved.relative_to(Path(watched).resolve())
            return True
        except ValueError:
            continue
    return False
