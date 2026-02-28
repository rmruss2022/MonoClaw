#!/usr/bin/env python3
"""
Interactive test for the window snap system.

Opens a small web page showing your display layout, then lets you
test snapping the frontmost window with keyboard shortcuts.

Usage:
    python3 test_snap.py

Then switch to the window you want to snap (e.g. Chrome) and press
the hotkey in the terminal:

  1 / 2 / 3 ... = snap to that zone
  0             = show layout + zones
  q             = quit
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ml.position_tracker import get_displays, get_total_bounds
from api.window_manager import get_frontmost_window, snap_window, check_accessibility


def print_layout(displays, total):
    print()
    print("=" * 60)
    print("  YOUR DISPLAY LAYOUT")
    print("=" * 60)
    print()

    for i, d in enumerate(displays):
        label = "MacBook" if d["x"] == 0 and d["width"] < 1600 else "External"
        print(f"  Monitor {i} ({label}): {d['width']}x{d['height']}")
        print(f"    origin: ({d['x']}, {d['y']})")
    print()
    print(f"  Total span: {total['width']}x{total['height']}")
    print()


def print_zones(displays):
    print("  SNAP ZONES:")
    print()
    idx = 1
    zones = []
    for i, d in enumerate(displays):
        label = f"Mon {i}"
        zones.append((idx, f"{label} full screen", i, "full"))
        idx += 1
        zones.append((idx, f"{label} left half", i, "half_left"))
        idx += 1
        zones.append((idx, f"{label} right half", i, "half_right"))
        idx += 1
        zones.append((idx, f"{label} top-left quarter", i, "quarter_tl"))
        idx += 1
        zones.append((idx, f"{label} top-right quarter", i, "quarter_tr"))
        idx += 1
        zones.append((idx, f"{label} bottom-left quarter", i, "quarter_bl"))
        idx += 1
        zones.append((idx, f"{label} bottom-right quarter", i, "quarter_br"))
        idx += 1

    for num, name, mon_idx, layout in zones:
        print(f"    [{num}] {name}")
    print()
    return zones


def main():
    if not check_accessibility():
        print("[ERROR] Accessibility permission not granted.")
        print("  System Settings > Privacy & Security > Accessibility")
        sys.exit(1)

    displays = get_displays()
    total = get_total_bounds(displays)

    print_layout(displays, total)
    zones = print_zones(displays)

    print("  INSTRUCTIONS:")
    print("    1. Switch to the window you want to test (e.g. click on Chrome)")
    print("    2. Come back to this terminal")
    print("    3. Type a zone number and press Enter to snap it")
    print("    4. Type 0 to reprint zones, q to quit")
    print()

    while True:
        try:
            choice = input("  Zone number (0=list, q=quit): ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if choice == "q":
            break
        if choice == "0":
            print_zones(displays)
            continue

        try:
            num = int(choice)
        except ValueError:
            print("    Invalid input")
            continue

        match = [z for z in zones if z[0] == num]
        if not match:
            print(f"    No zone {num}")
            continue

        _, name, mon_idx, layout = match[0]

        win = get_frontmost_window()
        if not win:
            print("    No frontmost window found — click on a window first")
            continue

        print(f"    Snapping '{win['owner']}' to {name}...")
        ok = snap_window(win["pid"], layout, displays[mon_idx])
        if ok:
            print(f"    Done! Check your screen.")
        else:
            print(f"    Failed — accessibility issue?")

    print("\n  Bye!")


if __name__ == "__main__":
    main()
