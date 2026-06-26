"""Pure folder analysis — no FastAPI or LLM dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from core.tools.handlers.filesystem import (
    _require_authorized_path,
    _SKIP_SEARCH_DIRS,
    PathNotAuthorizedError,
)

__all__ = [
    "FolderAnalysisResult",
    "analyze_folder",
    "count_indexed_under",
    "PathNotAuthorizedError",
]


@dataclass
class FolderAnalysisResult:
    path: str
    total_files: int = 0
    total_dirs: int = 0
    total_size_bytes: int = 0
    by_extension: dict[str, int] = field(default_factory=dict)
    largest_files: list[dict] = field(default_factory=list)
    tree_preview: str = ""
    indexed_files: int = 0
    indexed_paths: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _is_skipped(path: Path) -> bool:
    return any(part in _SKIP_SEARCH_DIRS for part in path.parts)


def analyze_folder(
    path: str,
    authorized_paths: list[str],
    *,
    max_depth: int = 4,
    max_files: int = 5000,
    max_preview_lines: int = 80,
    indexed_files: dict[str, float] | None = None,
) -> FolderAnalysisResult:
    resolved = Path(path).expanduser().resolve()
    _require_authorized_path(str(resolved), authorized_paths, operation="analizar")

    if not resolved.exists():
        raise ValueError(f"Path does not exist: {path}")
    if not resolved.is_dir():
        raise ValueError(f"Path is not a directory: {path}")

    result = FolderAnalysisResult(path=str(resolved))
    file_count = 0
    all_files: list[tuple[Path, int]] = []
    tree_lines: list[str] = []

    def _walk(current: Path, depth: int):
        nonlocal file_count
        if depth > max_depth:
            return
        try:
            entries = sorted(current.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            result.warnings.append(f"Permission denied: {current}")
            return

        indent = "  " * depth
        dirs_shown = 0
        for entry in entries:
            if _is_skipped(entry):
                continue

            if entry.is_dir():
                result.total_dirs += 1
                if depth < max_depth and len(tree_lines) < max_preview_lines:
                    tree_lines.append(f"{indent}{entry.name}/")
                _walk(entry, depth + 1)
            elif entry.is_file():
                if file_count >= max_files:
                    result.warnings.append(f"Truncated at {max_files} files")
                    return
                file_count += 1
                try:
                    stat = entry.stat()
                    size = stat.st_size
                except OSError:
                    continue
                result.total_size_bytes += size
                ext = entry.suffix.lower() or "(no ext)"
                result.by_extension[ext] = result.by_extension.get(ext, 0) + 1
                all_files.append((entry, size))
                if len(tree_lines) < max_preview_lines:
                    size_str = _format_size(size)
                    tree_lines.append(f"{indent}{entry.name}  ({size_str})")

    _walk(resolved, 0)
    result.total_files = file_count

    all_files.sort(key=lambda x: -x[1])
    result.largest_files = [
        {
            "path": str(p),
            "size_bytes": s,
            "modified": p.stat().st_mtime,
        }
        for p, s in all_files[:20]
    ]

    result.tree_preview = "\n".join(tree_lines[:max_preview_lines])

    if indexed_files:
        prefix = str(resolved)
        matches = [p for p in indexed_files if p.startswith(prefix)]
        result.indexed_files = len(matches)
        result.indexed_paths = matches[:50]

    return result


def count_indexed_under(path: str, indexed: dict[str, float]) -> tuple[int, list[str]]:
    prefix = str(Path(path).resolve())
    matches = [p for p in indexed if p.startswith(prefix)]
    return len(matches), matches[:50]


def _format_size(bytes_: int) -> str:
    if bytes_ < 1024:
        return f"{bytes_} B"
    elif bytes_ < 1024 * 1024:
        return f"{bytes_ / 1024:.1f} KB"
    else:
        return f"{bytes_ / (1024 * 1024):.1f} MB"
