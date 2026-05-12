"""macOS app integrations — Spotlight, Apple Notes, system notifications.

All functions return human-readable strings suitable for LLM consumption.
JXA scripts sanitize inputs via json.dumps to prevent JS injection.
"""

from __future__ import annotations

import json
import platform
import subprocess

from loguru import logger


def _run_jxa(script: str, timeout: int = 30) -> tuple[bool, str]:
    """Run a JXA script via osascript. Returns (success, output)."""
    try:
        result = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, "osascript timed out"
    except Exception as exc:
        return False, str(exc)

    if result.returncode != 0:
        return False, result.stderr.strip() or "osascript error"
    return True, result.stdout.strip()


def _run_applescript(script: str, timeout: int = 10) -> tuple[bool, str]:
    """Run an AppleScript snippet via osascript."""
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, "osascript timed out"
    except Exception as exc:
        return False, str(exc)

    if result.returncode != 0:
        return False, result.stderr.strip() or "osascript error"
    return True, result.stdout.strip()


_KIND_MAP = {
    "pdf": "kMDItemKind == 'PDF Document'",
    "image": "kMDItemContentTypeTree == 'public.image'",
    "text": "kMDItemContentTypeTree == 'public.plain-text'",
    "folder": "kMDItemContentType == 'public.folder'",
}


def spotlight_search(query: str, max_results: int = 10, kind: str | None = None) -> str:
    """Search the local filesystem using Spotlight (mdfind).

    Args:
        query: Search query string.
        max_results: Maximum number of results to return (default 10).
        kind: Optional file type filter — 'pdf', 'image', 'text', or 'folder'.
    """
    cmd = ["mdfind", "-limit", str(max_results)]

    if kind and kind.lower() in _KIND_MAP:
        cmd += ["-onlyin", "/", f"{_KIND_MAP[kind.lower()]} && {query}"]
    else:
        cmd += [query]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except subprocess.TimeoutExpired:
        return "Error: Spotlight search timed out"
    except Exception as exc:
        return f"Error running Spotlight search: {exc}"

    if result.returncode != 0:
        return f"Error: mdfind returned {result.returncode}: {result.stderr.strip()}"

    paths = [p for p in result.stdout.strip().splitlines() if p][:max_results]
    if not paths:
        return f"No Spotlight results for '{query}'"

    lines = [f"Spotlight results for '{query}' ({len(paths)} found):"]
    for p in paths:
        lines.append(f"  {p}")
    return "\n".join(lines)


_JXA_CREATE_NOTE = """\
var app = Application("Notes");
app.includeStandardAdditions = true;
var title = {title_json};
var body = {body_json};
var folderName = {folder_json};
var target;
try {{
    target = app.folders.byName(folderName);
    target.name(); // probe to verify it exists
}} catch(e) {{
    target = app.defaultAccount.folders[0];
}}
var note = app.Note({{name: title, body: body}});
target.notes.push(note);
"ok";
"""


def create_note(title: str, body: str, folder: str = "Notes") -> str:
    """Create a note in the Apple Notes app.

    Args:
        title: Note title.
        body: Note body content (plain text or HTML).
        folder: Folder name to save the note in (default: 'Notes').
    """
    if platform.system() != "Darwin":
        return f"Apple Notes is only available on macOS. Would have created: '{title}'"

    script = _JXA_CREATE_NOTE.format(
        title_json=json.dumps(title),
        body_json=json.dumps(body),
        folder_json=json.dumps(folder),
    )
    ok, output = _run_jxa(script)
    if not ok:
        logger.warning("create_note failed: {}", output)
        return f"Error creating note '{title}': {output}"
    return f"Note created: '{title}' in folder '{folder}'"


_JXA_SEARCH_NOTES = """\
var app = Application("Notes");
var kw = {kw_json};
var results = [];
app.notes().forEach(function(n) {{
    try {{
        var t = n.name() || "";
        var b = n.plaintext() || "";
        if (t.toLowerCase().indexOf(kw) >= 0 || b.toLowerCase().indexOf(kw) >= 0) {{
            results.push({{ title: t, snippet: b.substring(0, 200) }});
        }}
    }} catch(e) {{}}
}});
JSON.stringify(results.slice(0, {max_results}));
"""


def search_notes(query: str, max_results: int = 10) -> str:
    """Search Apple Notes by keyword (matches title and body).

    Args:
        query: Keyword to search for.
        max_results: Maximum number of results to return (default 10).
    """
    if platform.system() != "Darwin":
        return "Apple Notes is only available on macOS."

    kw = query.lower()
    script = _JXA_SEARCH_NOTES.format(
        kw_json=json.dumps(kw),
        max_results=max_results,
    )
    ok, output = _run_jxa(script)
    if not ok:
        logger.warning("search_notes failed: {}", output)
        return f"Error searching notes: {output}"

    try:
        data = json.loads(output)
    except Exception:
        return f"Error parsing Notes results for '{query}'"

    if not data:
        return f"No notes found matching '{query}'"

    lines = [f"Notes matching '{query}' ({len(data)} found):"]
    for item in data:
        lines.append(f"  [{item.get('title', '(untitled)')}] {item.get('snippet', '').strip()}")
    return "\n".join(lines)


def send_notification(title: str, message: str) -> str:
    """Send a macOS system notification.

    Args:
        title: Notification title.
        message: Notification body text.
    """
    if platform.system() != "Darwin":
        return f"System notifications are only available on macOS. Would have sent: '{title}'"

    safe_title = title.replace('"', '\\"')
    safe_message = message.replace('"', '\\"')
    script = f'display notification "{safe_message}" with title "{safe_title}" sound name "default"'

    ok, output = _run_applescript(script)
    if not ok:
        logger.warning("send_notification failed: {}", output)
        return f"Error sending notification: {output}"
    return f"Notification sent: '{title}'"
