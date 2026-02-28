"""
macOS Window Manager — enumerate, select, move, and snap windows.

Uses Quartz (CGWindowListCopyWindowInfo) to list windows and the
Accessibility API (AXUIElement) to move/resize them.

Requires Accessibility permission for the running process
(System Settings > Privacy & Security > Accessibility).
"""

import subprocess
from typing import Optional, Dict, List, Tuple

try:
    import Quartz
    from Quartz import (
        CGWindowListCopyWindowInfo,
        kCGWindowListOptionOnScreenOnly,
        kCGWindowListExcludeDesktopElements,
        kCGNullWindowID,
    )
    from AppKit import NSWorkspace
    HAS_QUARTZ = True
except ImportError:
    HAS_QUARTZ = False

try:
    from ApplicationServices import (
        AXUIElementCreateApplication,
        AXUIElementSetAttributeValue,
        AXUIElementCopyAttributeValue,
        AXValueCreate,
        kAXValueTypeCGPoint,
        kAXValueTypeCGSize,
    )
    HAS_AX = True
except ImportError:
    HAS_AX = False


SKIP_OWNERS = {
    "Window Server", "Dock", "SystemUIServer", "Control Center",
    "Notification Center", "Spotlight", "loginwindow",
}


def check_accessibility() -> bool:
    """Return True if the process has Accessibility permission."""
    if not HAS_AX:
        return False
    try:
        app_ref = AXUIElementCreateApplication(subprocess.os.getpid())
        return app_ref is not None
    except Exception:
        return False


def get_frontmost_app_pid() -> Optional[int]:
    """Return the PID of the frontmost (active) application."""
    if not HAS_QUARTZ:
        return None
    ws = NSWorkspace.sharedWorkspace()
    front_app = ws.frontmostApplication()
    if front_app is None:
        return None
    return front_app.processIdentifier()


def get_frontmost_window() -> Optional[Dict]:
    """Return info about the frontmost application's main window.

    Returns: {pid, owner, title, bounds: {x, y, w, h}} or None.
    """
    pid = get_frontmost_app_pid()
    if pid is None:
        return None

    options = kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements
    window_list = CGWindowListCopyWindowInfo(options, kCGNullWindowID)
    if not window_list:
        return None

    for win in window_list:
        owner = win.get("kCGWindowOwnerName", "")
        win_pid = win.get("kCGWindowOwnerPID", -1)
        if win_pid != pid:
            continue
        if owner in SKIP_OWNERS:
            continue
        layer = win.get("kCGWindowLayer", 999)
        if layer != 0:
            continue

        bounds = win.get("kCGWindowBounds", {})
        return {
            "pid": pid,
            "owner": owner,
            "title": win.get("kCGWindowName", ""),
            "bounds": {
                "x": int(bounds.get("X", 0)),
                "y": int(bounds.get("Y", 0)),
                "w": int(bounds.get("Width", 800)),
                "h": int(bounds.get("Height", 600)),
            },
        }

    return None


def _get_ax_window(pid: int):
    """Get the AXUIElement for the first window of the app at pid."""
    if not HAS_AX:
        return None
    app_ref = AXUIElementCreateApplication(pid)
    err, windows = AXUIElementCopyAttributeValue(app_ref, "AXWindows", None)
    if err != 0 or not windows or len(windows) == 0:
        return None
    return windows[0]


def move_and_resize(pid: int, x: int, y: int, w: int, h: int) -> bool:
    """Move and resize the frontmost window of the given PID.

    Returns True on success.
    """
    if not HAS_AX:
        print("[WindowManager] ApplicationServices not available")
        return False

    win = _get_ax_window(pid)
    if win is None:
        print(f"[WindowManager] No AX window for pid {pid}")
        return False

    pos = Quartz.CGPointMake(x, y)
    size = Quartz.CGSizeMake(w, h)
    pos_val = AXValueCreate(kAXValueTypeCGPoint, pos)
    size_val = AXValueCreate(kAXValueTypeCGSize, size)

    err1 = AXUIElementSetAttributeValue(win, "AXPosition", pos_val)
    err2 = AXUIElementSetAttributeValue(win, "AXSize", size_val)

    ok = err1 == 0 and err2 == 0
    if not ok:
        print(f"[WindowManager] AX errors: position={err1}, size={err2}")
    return ok


def snap_window(
    pid: int,
    layout: str,
    monitor: Dict,
) -> bool:
    """Snap the window to a layout zone on the given monitor rect.

    layout: "full", "half_left", "half_right",
            "quarter_tl", "quarter_tr", "quarter_bl", "quarter_br"
    monitor: {x, y, width, height} from position_tracker.get_displays()
    """
    mx, my = monitor["x"], monitor["y"]
    mw, mh = monitor["width"], monitor["height"]

    menu_bar = 25  # macOS menu bar height

    rects = {
        "full": (mx, my + menu_bar, mw, mh - menu_bar),
        "half_left": (mx, my + menu_bar, mw // 2, mh - menu_bar),
        "half_right": (mx + mw // 2, my + menu_bar, mw // 2, mh - menu_bar),
        "quarter_tl": (mx, my + menu_bar, mw // 2, (mh - menu_bar) // 2),
        "quarter_tr": (mx + mw // 2, my + menu_bar, mw // 2, (mh - menu_bar) // 2),
        "quarter_bl": (mx, my + menu_bar + (mh - menu_bar) // 2, mw // 2, (mh - menu_bar) // 2),
        "quarter_br": (mx + mw // 2, my + menu_bar + (mh - menu_bar) // 2, mw // 2, (mh - menu_bar) // 2),
    }

    rect = rects.get(layout)
    if rect is None:
        print(f"[WindowManager] Unknown layout: {layout}")
        return False

    x, y, w, h = rect
    return move_and_resize(pid, x, y, w, h)
