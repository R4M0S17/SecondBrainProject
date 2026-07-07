"""Desktop automation recorder — captures macOS input events via CGEventTap.

When ``pyobjc`` is unavailable, the recorder logs a warning and stores an
empty session.  The tools that call it will surface a clear error message
to the user.
"""

from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Any

from loguru import logger

try:
    import Quartz  # pyobjc-framework-Quartz

    HAS_QUARTZ = True
except ImportError:
    HAS_QUARTZ = False
    logger.warning("pyobjc not installed — Desktop Recorder will be unavailable")


# --------------------------------------------------------------------------- #
# Event model
# --------------------------------------------------------------------------- #

_EVENT_TYPE_NAMES: dict[int, str] = {
    1: "left_click",
    2: "left_click_up",
    3: "right_click",
    4: "right_click_up",
    10: "key_down",
    11: "key_up",
    12: "modifier",
}


@dataclass
class ActionEvent:
    """A single captured user action on macOS.

    Attributes:
        timestamp: Seconds since epoch.
        action_type: ``key_press``, ``click``, ``app_switch``, ``modifier``.
        key_code: Virtual key code (keyboard events only).
        key_char: Printable character (keyboard events only).
        mouse_x: Screen X coordinate (click events only).
        mouse_y: Screen Y coordinate (click events only).
        app_name: Active application name when the event fired.
        window_title: Frontmost window title (if available).
        modifiers: Bitmask of active modifier keys.
    """

    timestamp: float
    action_type: str
    key_code: int | None = None
    key_char: str | None = None
    mouse_x: float | None = None
    mouse_y: float | None = None
    app_name: str | None = None
    window_title: str | None = None
    modifiers: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "action_type": self.action_type,
            "key_code": self.key_code,
            "key_char": self.key_char,
            "mouse_x": self.mouse_x,
            "mouse_y": self.mouse_y,
            "app_name": self.app_name,
            "window_title": self.window_title,
            "modifiers": self.modifiers,
        }


# --------------------------------------------------------------------------- #
# Utility helpers
# --------------------------------------------------------------------------- #

# Maps Quartz virtual key codes to printable characters
_KEYCODE_MAP: dict[int, str] = {
    0: "a",
    1: "s",
    2: "d",
    3: "f",
    4: "h",
    5: "g",
    6: "z",
    7: "x",
    8: "c",
    9: "v",
    11: "b",
    12: "q",
    13: "w",
    14: "e",
    15: "r",
    16: "y",
    17: "t",
    18: "1",
    19: "2",
    20: "3",
    21: "4",
    22: "6",
    23: "5",
    24: "=",
    25: "9",
    26: "7",
    27: "-",
    28: "8",
    29: "0",
    30: "]",
    31: "o",
    32: "u",
    33: "[",
    34: "i",
    35: "p",
    36: "Return",
    37: "l",
    38: "j",
    39: "'",
    40: "k",
    41: ";",
    42: "\\",
    43: ",",
    44: "/",
    45: "n",
    46: "m",
    47: ".",
    48: "Tab",
    49: "Space",
    50: "`",
    51: "Delete",
    53: "Escape",
    55: "Command",
    56: "Shift",
    57: "CapsLock",
    58: "Option",
    59: "Control",
    60: "RightShift",
    61: "RightOption",
    62: "RightControl",
    63: "Fn",
}


def _active_app_name() -> str | None:
    """Get the frontmost application name via AppleScript."""
    try:
        result = subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "System Events" to get name of first process whose frontmost is true',
            ],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        return result.stdout.strip() or None
    except Exception:
        return None


def _active_window_title() -> str | None:
    """Get the frontmost window title via AppleScript."""
    try:
        result = subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "System Events" to get title of first window of first process whose frontmost is true',
            ],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        return result.stdout.strip() or None
    except Exception:
        return None


def _is_click_on_cerebro_window(x: float, y: float) -> bool:
    """Check if screen coordinates fall within any Cerebro window.

    Uses CGWindowListCopyWindowInfo for reliable hit-testing regardless of
    which app is frontmost.  This prevents clicks on the recording overlay
    from being captured even when the overlay is not the key window.
    """
    if not HAS_QUARTZ:
        return False
    try:
        from Quartz import (
            CGWindowListCopyWindowInfo,
            kCGNullWindowID,
            kCGWindowListOptionAll,
        )

        # Use kCGWindowListOptionAll to include windows that may have just been hidden
        # (like the recording overlay when stop is clicked)
        windows = CGWindowListCopyWindowInfo(kCGWindowListOptionAll, kCGNullWindowID)
        if not windows:
            return False
        for win_info in windows:
            owner = str(win_info.get("kCGWindowOwnerName", "")).lower()
            window_name = str(win_info.get("kCGWindowName", "")).lower()
            # Check if this is any Cerebro window (main or recording overlay)
            # Use case-insensitive comparison to handle variations
            if "cerebro" in owner or "cerebro" in window_name:
                bounds = win_info.get("kCGWindowBounds", {})
                wx = bounds.get("X", 0)
                wy = bounds.get("Y", 0)
                ww = bounds.get("Width", 0)
                wh = bounds.get("Height", 0)
                if wx <= x <= wx + ww and wy <= y <= wy + wh:
                    logger.debug(
                        f"Filtered click on Cerebro window at ({x}, {y}) - owner: {owner}, name: {window_name}"
                    )
                    return True
        return False
    except Exception as e:
        logger.debug(f"Error checking Cerebro window: {e}")
        return False


def _app_at_coordinates(x: float, y: float) -> str | None:
    """Get the app name at the given screen coordinates.

    Uses CGWindowListCopyWindowInfo to find which app owns the window at (x, y).
    This is more reliable than _active_app_name() for determining the target app
    of a click, especially when the click triggers an app activation.
    Only returns names of user applications that can be activated via AppleScript.
    """
    if not HAS_QUARTZ:
        return None

    # System processes that are not activatable apps
    SYSTEM_PROCESSES = frozenset(
        {
            "Window Server",
            "Dock",
            "SystemUIServer",
            "loginwindow",
            "Finder",  # Finder is handled specially - clicks on Dock icons open apps
            "NotificationCenter",
            "ControlCenter",
            "Spotlight",
            "Siri",
            "Wallpaper",  # macOS wallpaper/desktop
        }
    )

    try:
        from AppKit import NSRunningApplication
        from Quartz import (
            CGWindowListCopyWindowInfo,
            kCGNullWindowID,
            kCGWindowListOptionOnScreenOnly,
        )

        windows = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
        if not windows:
            return None
        for win_info in reversed(windows):
            owner = win_info.get("kCGWindowOwnerName", "")
            owner_pid = win_info.get("kCGWindowOwnerPID", 0)
            # Skip system processes that can't be activated via AppleScript
            if owner in SYSTEM_PROCESSES:
                continue
            # Verify this is a real user application by checking if it has a bundle identifier
            # This filters out system processes that aren't in our hardcoded list
            try:
                running_app = NSRunningApplication.runningApplicationWithProcessIdentifier_(
                    owner_pid
                )
                if running_app is None:
                    continue
                bundle_id = running_app.bundleIdentifier()
                # System processes typically don't have bundle identifiers or have special ones
                if not bundle_id or bundle_id.startswith("com.apple."):
                    # Allow some Apple apps that are user-facing
                    if bundle_id not in (
                        "com.apple.finder",
                        "com.apple.safari",
                        "com.apple.notes",
                        "com.apple.textedit",
                        "com.apple.calculator",
                        "com.apple.Preview",
                        "com.apple.mail",
                    ):
                        continue
            except Exception:
                # If we can't verify, skip this window
                continue
            bounds = win_info.get("kCGWindowBounds", {})
            wx = bounds.get("X", 0)
            wy = bounds.get("Y", 0)
            ww = bounds.get("Width", 0)
            wh = bounds.get("Height", 0)
            if wx <= x <= wx + ww and wy <= y <= wy + wh:
                return owner if owner else None
        return None
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Recorder
# --------------------------------------------------------------------------- #

# This global is set by the CGEventTap callback so we can access it without
# the closure overhead that pyobjc sometimes struggles with.
_recorder_instance: Recorder | None = None


def _cg_callback(proxy: Any, event_type: int, event: Any, refcon: Any) -> Any:
    """CGEventTap callback — forwards events to the active Recorder instance."""
    inst = _recorder_instance
    if inst is not None and inst._running:
        inst._handle_event(event_type, event)
    return event


# --------------------------------------------------------------------------- #
# Accessibility Permission Detection
# --------------------------------------------------------------------------- #


def check_accessibility_permission() -> bool:
    """Check if current process has Accessibility permission on macOS.

    Uses the official AXIsProcessTrusted() API — works on all macOS versions.
    """
    if not HAS_QUARTZ:
        return False

    try:
        from ApplicationServices import AXIsProcessTrusted

        return bool(AXIsProcessTrusted())
    except Exception as e:
        logger.debug(f"Could not check accessibility permission: {e}")
        return False


def request_accessibility_permission() -> None:
    """Open macOS System Preferences Accessibility panel."""
    try:
        subprocess.run(
            [
                "open",
                "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
            ],
            timeout=5,
            check=False,
        )
        logger.info("Opened System Preferences Accessibility panel")
    except Exception as e:
        logger.error(f"Could not open System Preferences: {e}")


EXCLUDED_APPS = frozenset(
    {"Cerebro", "cerebro", "Cerebro Recording", "Electron", "python3", "python3.14"}
)


class Recorder:
    """Captures macOS input events while recording is active.

    Usage::

        rec = Recorder()
        rec.start()
        # ... user performs actions ...
        events = rec.stop()
        print(f"Captured {len(events)} events")
    """

    def __init__(self) -> None:
        self._events: list[ActionEvent] = []
        self._running = False
        self._started_at: float | None = None
        self._thread: threading.Thread | None = None
        self._tap: Any = None
        self._lock = threading.Lock()
        self._last_click: ActionEvent | None = None  # for double-click merge
        self._ready: threading.Event | None = None  # Señal para esperar tap listo
        self._run_loop_ref: Any = None  # Referencia al CFRunLoop del thread

        if HAS_QUARTZ:
            trusted = check_accessibility_permission()
            logger.info(f"Accessibility permission on init: {trusted}")
        else:
            logger.warning("pyobjc not installed — Recorder unavailable")

    @property
    def is_recording(self) -> bool:
        return self._running

    @property
    def event_count(self) -> int:
        return len(self._events)

    @property
    def started_at(self) -> float | None:
        return self._started_at

    @property
    def duration_sec(self) -> float:
        if self._started_at is None:
            return 0.0
        return max(0.0, time.time() - self._started_at)

    def get_events(self) -> list[ActionEvent]:
        with self._lock:
            return list(self._events)

    def get_unique_apps(self) -> list[str]:
        apps: list[str] = []
        seen: set[str] = set()
        for ev in self.get_events():
            name = ev.app_name
            if name and name not in seen:
                seen.add(name)
                apps.append(name)
        return apps

    def start(self) -> None:
        """Begin capturing input events."""
        if self._running:
            return
        if not HAS_QUARTZ:
            raise RuntimeError("recorder_unavailable")
        if not check_accessibility_permission():
            request_accessibility_permission()
            raise RuntimeError("accessibility_required")
        self._events = []
        self._started_at = time.time()
        self._running = True
        self._ready = threading.Event()
        self._run_loop_ref = None
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        # Esperar a que el CGEventTap esté configurado y listo para capturar
        if not self._ready.wait(timeout=2.0):
            logger.warning("CGEventTap took too long to initialize")
        logger.info("Desktop Recorder started")

    def stop(self) -> list[ActionEvent]:
        """Stop capturing and return all recorded events."""
        self._running = False
        if self._tap is not None and HAS_QUARTZ:
            try:
                Quartz.CGEventTapEnable(self._tap, False)
            except Exception:
                pass
        # Detener el run loop del thread del recorder (no del main thread)
        if self._run_loop_ref is not None and HAS_QUARTZ:
            try:
                Quartz.CFRunLoopStop(self._run_loop_ref)
            except Exception:
                pass
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        logger.info("Desktop Recorder stopped — {} events", len(self._events))
        self._started_at = None
        self._ready = None
        self._run_loop_ref = None
        return list(self._events)

    def cancel(self) -> None:
        """Stop recording and discard captured events."""
        self._running = False
        if self._tap is not None and HAS_QUARTZ:
            try:
                Quartz.CGEventTapEnable(self._tap, False)
            except Exception:
                pass
        if self._run_loop_ref is not None and HAS_QUARTZ:
            try:
                Quartz.CFRunLoopStop(self._run_loop_ref)
            except Exception:
                pass
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        self._events = []
        self._started_at = None
        self._ready = None
        self._run_loop_ref = None
        logger.info("Desktop Recorder cancelled")

    def _handle_event(self, event_type: int, event: Any) -> None:
        """Process a single CGEvent and append to the event list."""
        now = time.time()
        etype_name = _EVENT_TYPE_NAMES.get(event_type, f"unknown_{event_type}")

        modifiers = 0
        if HAS_QUARTZ:
            try:
                flags = Quartz.CGEventGetFlags(event)
                modifiers = flags
            except Exception:
                pass

        key_code = None
        key_char = None
        mouse_x = None
        mouse_y = None
        app_name: str | None = None
        window_title: str | None = None

        if event_type in (10, 11):  # key down/up
            if HAS_QUARTZ:
                try:
                    kc = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
                    key_code = int(kc)
                    key_char = _KEYCODE_MAP.get(key_code)
                except Exception:
                    pass
            # For keyboard events, use the frontmost app
            app_name = _active_app_name()
            window_title = _active_window_title()
            # Filter keyboard events from our own UI
            if app_name and app_name in EXCLUDED_APPS:
                return
        elif event_type in (1, 2, 3, 4):  # mouse clicks
            if HAS_QUARTZ:
                try:
                    loc = Quartz.CGEventGetLocation(event)
                    mouse_x = round(loc.x, 1)
                    mouse_y = round(loc.y, 1)
                except Exception:
                    pass
            # For mouse clicks, use coordinate-based filtering and app detection.
            # This is more reliable than _active_app_name() because:
            # 1. It correctly identifies clicks on the overlay (filter them out)
            # 2. It correctly identifies clicks on other apps (Dock, etc.) even if
            #    the frontmost app hasn't changed yet (e.g., clicking Finder in Dock
            #    while Cerebro is still frontmost)
            if mouse_x is not None and mouse_y is not None:
                if _is_click_on_cerebro_window(mouse_x, mouse_y):
                    return
                # Determine the app at the click coordinates
                app_name = _app_at_coordinates(mouse_x, mouse_y)
            else:
                # Fallback if we couldn't get coordinates
                app_name = _active_app_name()
                window_title = _active_window_title()
                if app_name and app_name in EXCLUDED_APPS:
                    return

        ev = ActionEvent(
            timestamp=now,
            action_type=etype_name,
            key_code=key_code,
            key_char=key_char,
            mouse_x=mouse_x,
            mouse_y=mouse_y,
            app_name=app_name,
            window_title=window_title,
            modifiers=modifiers,
        )

        with self._lock:
            # ── Double-click merge ──────────────────────────────────────────
            # If two left clicks at the same position arrive within 300ms,
            # merge them into a single "double_click" event.
            if (
                etype_name == "left_click"
                and self._last_click is not None
                and self._last_click.action_type == "left_click"
                and self._last_click.mouse_x == mouse_x
                and self._last_click.mouse_y == mouse_y
                and now - self._last_click.timestamp < 0.3
            ):
                # Replace the previous click with a double click, skip current
                self._last_click.action_type = "double_click"
                self._last_click.timestamp = now
                self._last_click = None
                return

            if etype_name in ("left_click", "right_click", "double_click"):
                self._last_click = ev
            else:
                self._last_click = None

            self._events.append(ev)

    def _run_loop(self) -> None:
        """Background thread: sets up CGEventTap and enters CFRunLoop."""
        if not HAS_QUARTZ:
            return

        global _recorder_instance
        _recorder_instance = self

        try:
            # Mask: key down + left mouse down + mouse drag
            mask = (
                Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown)
                | Quartz.CGEventMaskBit(Quartz.kCGEventLeftMouseDown)
                | Quartz.CGEventMaskBit(Quartz.kCGEventRightMouseDown)
                | Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged)
            )
            tap = Quartz.CGEventTapCreate(
                Quartz.kCGHIDEventTap,
                Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionDefault,
                mask,
                _cg_callback,
                None,
            )
            if tap is None:
                logger.warning(
                    "CGEventTapCreate returned NULL — "
                    "check Accessibility permissions in System Settings"
                )
                if self._ready:
                    self._ready.set()
                return

            self._tap = tap
            source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
            loop = Quartz.CFRunLoopGetCurrent()
            self._run_loop_ref = loop  # Guardar referencia para detener correctamente
            Quartz.CFRunLoopAddSource(loop, source, Quartz.kCFRunLoopDefaultMode)
            Quartz.CGEventTapEnable(tap, True)

            # Señalizar que el tap está configurado y listo para capturar
            if self._ready:
                self._ready.set()

            # Run until stopped
            Quartz.CFRunLoopRun()
        except Exception as exc:
            logger.exception("Recorder run loop crashed: {}", exc)
            if self._ready:
                self._ready.set()
        finally:
            _recorder_instance = None
