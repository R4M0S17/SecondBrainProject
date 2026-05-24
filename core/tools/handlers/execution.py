from __future__ import annotations

import collections  # noqa: F401 — pre-loaded so sandbox import doesn't trigger sub-imports
import datetime  # noqa: F401
import itertools  # noqa: F401
import json  # noqa: F401
import math  # noqa: F401
import re  # noqa: F401
import subprocess
import sys
import threading
from pathlib import Path

from loguru import logger
from RestrictedPython import compile_restricted, safe_builtins, safe_globals

from core.tools.handlers.filesystem import PathNotAuthorizedError, validate_path

# `time` is not in the spec's explicit list but is a transitive dependency of
# `datetime` in Python 3.14 (deferred imports cause __import__('time') on each
# call to datetime.date.today()). It provides only timing functions — no
# filesystem or network access — so it is safe to allow.
ALLOWED_MODULES = frozenset({"math", "datetime", "json", "re", "collections", "itertools", "time"})
MAX_OUTPUT_CHARS = 4000


def _make_safe_import(allowed: frozenset):
    # RestrictedPython's `compile_restricted` transforms:
    #   print(x)  →  _print = _print_(_getattr_); _print._call_print(x)
    # Our _import is called for every `import` in sandbox code.
    # We return from sys.modules (already cached by the top-level imports above)
    # so that allowed modules never need to load sub-dependencies at runtime.
    def _import(name, *args, **kwargs):
        top = name.split(".")[0]
        if top not in allowed:
            raise ImportError(f"Import of '{name}' is not allowed in sandbox")
        if name in sys.modules:
            return sys.modules[name]
        # Fallback: should rarely reach here given the top-level imports above
        import importlib

        return importlib.import_module(name)

    return _import


def execute_python(code: str, timeout_seconds: int = 10) -> str:
    try:
        byte_code = compile_restricted(code, "<sandbox>", "exec")
    except SyntaxError as exc:
        return f"SyntaxError: {exc}"

    output_parts: list[str] = []
    error: list[str] = []

    # RestrictedPython compiles `print(x)` to:
    #   _print = _print_(_getattr_)   ← instantiation; _getattr_ is safe_getattr
    #   _print._call_print(x)         ← actual output; THIS is where we capture
    class _Printer:
        def __init__(self, _getattr_=None) -> None:
            pass

        def _call_print(self, *args, **kwargs) -> _Printer:
            sep = kwargs.get("sep", " ")
            end = kwargs.get("end", "\n")
            output_parts.append(sep.join(str(a) for a in args) + end)
            return self

    def run() -> None:
        builtins = dict(safe_builtins)
        builtins["__import__"] = _make_safe_import(ALLOWED_MODULES)
        for blocked in ("open", "exec", "eval", "compile", "input", "breakpoint"):
            builtins.pop(blocked, None)

        globs = {**safe_globals, "__builtins__": builtins, "_print_": _Printer}
        try:
            exec(byte_code, globs)  # noqa: S102
        except Exception as exc:
            error.append(f"{type(exc).__name__}: {exc}")

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(timeout_seconds)

    if thread.is_alive():
        logger.warning("execute_python: timeout after {}s", timeout_seconds)
        return f"TimeoutError: execution exceeded {timeout_seconds}s"

    if error:
        return f"Error: {error[0]}"

    return "".join(output_parts)[:MAX_OUTPUT_CHARS]


def run_script(filepath: str, authorized_paths: list[str], timeout_seconds: int = 30) -> str:
    if not validate_path(filepath, authorized_paths):
        raise PathNotAuthorizedError(filepath, authorized_paths, operation="ejecutar")
    p = Path(filepath)
    if not p.exists():
        return f"Error: file not found: {filepath}"
    try:
        result = subprocess.run(
            ["python3", str(p)],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        output = result.stdout + result.stderr
        return output[:MAX_OUTPUT_CHARS] or "(no output)"
    except subprocess.TimeoutExpired:
        return f"TimeoutError: script exceeded {timeout_seconds}s"
    except OSError as exc:
        return f"Error running script: {exc}"
