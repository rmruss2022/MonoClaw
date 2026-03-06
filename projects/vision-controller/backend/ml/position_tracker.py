"""
Maps normalized hand landmark positions to screen coordinates across multiple monitors.

Uses Quartz CGDisplayBounds to enumerate displays and map the hand's (x, y) from
the camera's 0-1 normalized space to an absolute pixel coordinate on the correct monitor.
"""

from typing import List, Tuple, Dict, Optional

try:
    import Quartz
    HAS_QUARTZ = True
except ImportError:
    HAS_QUARTZ = False


def get_displays() -> List[Dict]:
    """Return a list of display rects sorted left-to-right by x origin.

    Each entry: {id, x, y, width, height} in global pixel coordinates.
    """
    if not HAS_QUARTZ:
        return [{"id": 0, "x": 0, "y": 0, "width": 1920, "height": 1080}]

    displays = []
    max_displays = 16
    (err, active_ids, count) = Quartz.CGGetActiveDisplayList(max_displays, None, None)
    if err != 0:
        return [{"id": 0, "x": 0, "y": 0, "width": 1920, "height": 1080}]

    for did in active_ids:
        bounds = Quartz.CGDisplayBounds(did)
        displays.append({
            "id": int(did),
            "x": int(bounds.origin.x),
            "y": int(bounds.origin.y),
            "width": int(bounds.size.width),
            "height": int(bounds.size.height),
        })

    displays.sort(key=lambda d: d["x"])
    return displays


def get_total_bounds(displays: List[Dict]) -> Dict:
    """Compute the bounding rectangle spanning all displays."""
    if not displays:
        return {"x": 0, "y": 0, "width": 1920, "height": 1080}
    min_x = min(d["x"] for d in displays)
    min_y = min(d["y"] for d in displays)
    max_x = max(d["x"] + d["width"] for d in displays)
    max_y = max(d["y"] + d["height"] for d in displays)
    return {"x": min_x, "y": min_y, "width": max_x - min_x, "height": max_y - min_y}


def palm_center(landmarks: List[Tuple[float, float, float]]) -> Tuple[float, float]:
    """Return the normalized (x, y) average of the wrist and four MCP joints."""
    indices = [0, 5, 9, 13, 17]
    sx = sum(landmarks[i][0] for i in indices) / len(indices)
    sy = sum(landmarks[i][1] for i in indices) / len(indices)
    return (sx, sy)


def hand_to_screen(
    landmarks: List[Tuple[float, float, float]],
    displays: Optional[List[Dict]] = None,
) -> Dict:
    """Convert hand landmarks to screen position and zone info.

    The camera image is mirrored (webcam convention), so we flip X:
    hand x=0 (left of camera) maps to the right edge of the total screen span,
    hand x=1 (right of camera) maps to the left edge.

    Returns:
        {
            screen_x, screen_y: absolute pixel coords,
            norm_x, norm_y: 0-1 across total display span,
            monitor_idx: which display the hand points at,
            zone: "left" | "right" | "top_left" | "top_right" | "bottom_left" | "bottom_right"
        }
    """
    if displays is None:
        displays = get_displays()
    total = get_total_bounds(displays)

    px, py = palm_center(landmarks)
    norm_x = 1.0 - px  # mirror
    norm_y = py

    screen_x = total["x"] + norm_x * total["width"]
    screen_y = total["y"] + norm_y * total["height"]

    monitor_idx = 0
    for i, d in enumerate(displays):
        if d["x"] <= screen_x < d["x"] + d["width"]:
            monitor_idx = i
            break

    disp = displays[monitor_idx]
    local_x = (screen_x - disp["x"]) / disp["width"]
    local_y = (screen_y - disp["y"]) / disp["height"]

    if local_x < 0.5 and local_y < 0.5:
        zone = "top_left"
    elif local_x >= 0.5 and local_y < 0.5:
        zone = "top_right"
    elif local_x < 0.5:
        zone = "bottom_left"
    else:
        zone = "bottom_right"

    half = "left" if local_x < 0.5 else "right"

    return {
        "screen_x": int(screen_x),
        "screen_y": int(screen_y),
        "norm_x": round(norm_x, 4),
        "norm_y": round(norm_y, 4),
        "monitor_idx": monitor_idx,
        "zone": zone,
        "half": half,
    }
