from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from loguru import logger


class PathNotAuthorizedError(Exception):
    pass


def validate_path(path: str, authorized_paths: list[str]) -> bool:
    """Return True if path resolves to within any of the authorized_paths."""
    resolved = Path(path).resolve()
    for auth in authorized_paths:
        try:
            resolved.relative_to(Path(auth).resolve())
            return True
        except ValueError:
            continue
    return False


def read_file(path: str, authorized_paths: list[str]) -> str:
    if not validate_path(path, authorized_paths):
        raise PathNotAuthorizedError(f"Path '{path}' is not within authorized paths")
    p = Path(path)
    if not p.exists():
        return f"Error: file not found: {path}"
    if not p.is_file():
        return f"Error: not a file: {path}"
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"Error reading file: {exc}"


def write_file(path: str, content: str, authorized_paths: list[str]) -> bool:
    if not validate_path(path, authorized_paths):
        raise PathNotAuthorizedError(f"Path '{path}' is not within authorized paths")
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        logger.info("write_file: wrote {} bytes to {}", len(content), path)
        return True
    except OSError as exc:
        logger.error("write_file failed: {}", exc)
        return False


def create_directory(path: str, authorized_paths: list[str]) -> bool:
    if not validate_path(path, authorized_paths):
        raise PathNotAuthorizedError(f"Path '{path}' is not within authorized paths")
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        logger.info("create_directory: {}", path)
        return True
    except OSError as exc:
        logger.error("create_directory failed: {}", exc)
        return False


def list_directory(path: str, authorized_paths: list[str]) -> list[str]:
    if not validate_path(path, authorized_paths):
        raise PathNotAuthorizedError(f"Path '{path}' is not within authorized paths")
    p = Path(path)
    if not p.exists():
        return []
    if not p.is_dir():
        return [str(p)]
    return [str(child) for child in sorted(p.iterdir())]


def search_files(
    pattern: str,
    authorized_paths: list[str],
    base_path: str | None = None,
    extension: str | None = None,
    max_results: int = 20,
) -> str:
    """Recursively search for files matching pattern within authorized paths.

    Returns formatted list with size and modification date for each match.
    """
    start = Path(base_path or authorized_paths[0]).expanduser().resolve()
    if not validate_path(str(start), authorized_paths):
        raise PathNotAuthorizedError(f"base_path '{start}' is not within authorized paths")
    if not start.exists():
        return f"Directory not found: {start}"

    ext = extension.lower() if extension else None
    matches: list[str] = []
    for p in start.rglob(pattern):
        if not p.is_file():
            continue
        if ext and p.suffix.lower() != ext:
            continue
        if not validate_path(str(p), authorized_paths):
            continue
        try:
            stat = p.stat()
            modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            size_kb = stat.st_size / 1024
            matches.append(f"{p}  ({size_kb:.1f} KB, modified {modified})")
        except OSError:
            matches.append(str(p))
        if len(matches) >= max_results:
            break

    if not matches:
        return f"No files found matching '{pattern}' in {start}"
    return "\n".join(matches)


def create_python_file(filename: str, code: str, authorized_paths: list[str]) -> str:
    if not filename.endswith(".py"):
        return "Error: filename must have a .py extension"
    if "/" in filename or "\\" in filename:
        return "Error: filename must not contain path separators"
    base = Path(authorized_paths[0]).expanduser().resolve()
    dest = base / filename
    if not validate_path(str(dest), authorized_paths):
        raise PathNotAuthorizedError(f"Destination '{dest}' is not within authorized paths")
    try:
        base.mkdir(parents=True, exist_ok=True)
        dest.write_text(code, encoding="utf-8")
        logger.info("create_python_file: wrote {} to {}", filename, dest)
        return f"Python file created: {dest}"
    except OSError as exc:
        return f"Error creating file: {exc}"


def delete_file(path: str, authorized_paths: list[str]) -> str:
    if not validate_path(path, authorized_paths):
        raise PathNotAuthorizedError(f"Path '{path}' is not within authorized paths")
    p = Path(path).resolve()
    if not p.exists():
        return f"Error: file not found: {path}"
    if not p.is_file():
        return f"Error: not a regular file: {path}"
    try:
        # Move to Trash instead of hard delete (safer on macOS)
        subprocess.run(
            ["osascript", "-e", f'tell application "Finder" to delete POSIX file "{p}"'],
            check=True,
            capture_output=True,
        )
        logger.info("delete_file: moved {} to Trash", p)
        return f"File moved to Trash: {p}"
    except subprocess.CalledProcessError as exc:
        return f"Error deleting file: {exc.stderr.decode().strip() or exc}"
