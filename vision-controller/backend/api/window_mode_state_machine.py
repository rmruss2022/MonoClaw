"""
State machine for gesture-driven window management.

States:
  idle      — no window selected, waiting for 'point' gesture
  selected  — window locked, reading gesture + hand position each frame
  (deselect via 'stop' gesture)

Finger-count → layout mapping:
  point (1 finger)        → full screen
  peace (2 fingers)       → half screen (left/right by hand position)
  four_fingers (4 fingers) → quarter screen (quadrant by hand position)

Hand position determines which monitor and which zone.
"""

import time
from typing import Optional, Dict, List, Tuple

from ml.position_tracker import get_displays, hand_to_screen
from api.window_manager import get_frontmost_window, snap_window


GESTURE_TO_LAYOUT = {
    "point": "full",
    "peace": "half",
    "four_fingers": "quarter",
}

DEBOUNCE_SEC = 0.35
SNAP_COOLDOWN_SEC = 0.6


class WindowModeStateMachine:
    """Tracks window selection state and maps gestures to snap commands."""

    def __init__(self):
        self.state = "idle"
        self.selected_pid: Optional[int] = None
        self.selected_owner: Optional[str] = None
        self.displays: List[Dict] = []
        self.last_snap_time: float = 0
        self.last_layout: Optional[str] = None
        self.last_monitor_idx: int = -1
        self.last_zone: Optional[str] = None
        self._gesture_start_time: float = 0
        self._pending_gesture: Optional[str] = None
        self._refresh_displays()

    def _refresh_displays(self):
        self.displays = get_displays()

    def process(
        self,
        gesture: Optional[str],
        confidence: float,
        landmarks: Optional[List[Tuple[float, float, float]]],
    ) -> Dict:
        """Process one frame of gesture + landmark data.

        Returns a status dict for logging/WebSocket broadcast.
        """
        if gesture == "stop" and self.state != "idle":
            return self._deselect()

        if gesture == "fist" or gesture == "thumbs_up" or gesture == "unknown" or gesture is None:
            self._pending_gesture = None
            if self.state == "idle":
                return {"action": "none", "state": self.state}
            return {"action": "holding", "state": self.state, "pid": self.selected_pid, "owner": self.selected_owner}

        if self.state == "idle":
            if gesture in GESTURE_TO_LAYOUT:
                return self._try_select(gesture, landmarks)
            return {"action": "none", "state": self.state}

        if self.state == "selected":
            if gesture in GESTURE_TO_LAYOUT and landmarks:
                return self._try_snap(gesture, landmarks)
            return {"action": "holding", "state": self.state, "pid": self.selected_pid, "owner": self.selected_owner}

        return {"action": "none", "state": self.state}

    def _try_select(self, gesture: str, landmarks) -> Dict:
        """Attempt to select the frontmost window after debounce."""
        now = time.time()
        if self._pending_gesture != gesture:
            self._pending_gesture = gesture
            self._gesture_start_time = now
            return {"action": "debouncing", "state": "idle", "gesture": gesture}

        if now - self._gesture_start_time < DEBOUNCE_SEC:
            return {"action": "debouncing", "state": "idle", "gesture": gesture}

        win = get_frontmost_window()
        if win is None:
            return {"action": "no_window", "state": "idle"}

        self.state = "selected"
        self.selected_pid = win["pid"]
        self.selected_owner = win["owner"]
        self._refresh_displays()
        self._pending_gesture = None

        result = {
            "action": "selected",
            "state": self.state,
            "pid": self.selected_pid,
            "owner": self.selected_owner,
            "title": win.get("title", ""),
        }

        if landmarks:
            snap_result = self._try_snap(gesture, landmarks)
            result["snap"] = snap_result

        return result

    def _try_snap(self, gesture: str, landmarks) -> Dict:
        """Determine layout from gesture and zone from hand position, then snap."""
        pos = hand_to_screen(landmarks, self.displays)
        monitor_idx = pos["monitor_idx"]
        base_layout = GESTURE_TO_LAYOUT.get(gesture, "full")

        if base_layout == "full":
            layout = "full"
        elif base_layout == "half":
            layout = f"half_{pos['half']}"
        elif base_layout == "quarter":
            layout = f"quarter_{pos['zone'][:2] if '_' in pos['zone'] else pos['zone']}"
            zone = pos["zone"]
            abbrev = {"top_left": "tl", "top_right": "tr", "bottom_left": "bl", "bottom_right": "br"}
            layout = f"quarter_{abbrev.get(zone, 'tl')}"
        else:
            layout = "full"

        now = time.time()
        same_snap = (layout == self.last_layout and monitor_idx == self.last_monitor_idx)
        if same_snap and (now - self.last_snap_time) < SNAP_COOLDOWN_SEC:
            return {
                "action": "snap_held",
                "layout": layout,
                "monitor_idx": monitor_idx,
                "zone": pos["zone"],
            }

        if monitor_idx < len(self.displays):
            monitor = self.displays[monitor_idx]
        else:
            monitor = self.displays[0] if self.displays else {"x": 0, "y": 0, "width": 1920, "height": 1080}

        ok = snap_window(self.selected_pid, layout, monitor)
        self.last_snap_time = now
        self.last_layout = layout
        self.last_monitor_idx = monitor_idx
        self.last_zone = pos["zone"]

        return {
            "action": "snapped" if ok else "snap_failed",
            "layout": layout,
            "monitor_idx": monitor_idx,
            "zone": pos["zone"],
            "screen_x": pos["screen_x"],
            "screen_y": pos["screen_y"],
        }

    def _deselect(self) -> Dict:
        """Release the selected window and return to idle."""
        prev_owner = self.selected_owner
        self.state = "idle"
        self.selected_pid = None
        self.selected_owner = None
        self.last_layout = None
        self.last_monitor_idx = -1
        self._pending_gesture = None
        return {
            "action": "deselected",
            "state": "idle",
            "prev_owner": prev_owner,
        }
