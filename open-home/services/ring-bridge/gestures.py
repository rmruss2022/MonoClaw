#!/usr/bin/env python3
"""
openhome ring gestures — a pure state machine over accelerometer samples.

No Bluetooth in this file, on purpose. Everything here is a function of
(x, y, z, t), which means the whole thing is testable against synthetic traces
with no ring present — see test_gestures.py. When the real ring arrives the only
new thing is where the samples come from.

WHAT WE TOOK FROM THE PRIOR ART

Georgescortas/ring_control got several things right and we keep them:

  - Auto-calibrate the resting magnitude instead of hard-coding 1g. The ring
    reads ~8192 counts per g, but the rest value drifts per unit and per
    temperature.
  - Adapt that rest value ONLY while quiet, so a gesture never moves the
    reference it is being measured against.
  - Hysteresis: after a jolt, the signal must fall back inside a release band
    before the next jolt counts. Without it one tap rings as three.
  - Read hand ORIENTATION from before the gesture started, not during it. A
    moving hand produces samples that look like pure gravity mid-swing while
    the wrist has already turned — so that reading is a confident lie.

WHAT WE DO DIFFERENTLY

  - ONE mechanism for all tap counts. ring_control has separate "single" and
    "double" modes and fires the moment the second tap lands. We count jolts
    into a burst and fire when the burst ENDS, which gives double and triple
    from the same code and makes "was that two or three" a real question we can
    answer instead of a race.
  - A MODAL music mode. Double tap opens a window; while it is open, wrist roll
    maps to volume; it closes on idle. Continuous controls cannot be always-live
    — a hand rotates constantly and you would be setting the volume all day.
  - Roll comes out of atan2 on the gravity vector, which is an absolute angle
    rather than a magnitude deviation, so it works as a knob rather than a
    trigger.

THE SAMPLE RATE PROBLEM, STATED HONESTLY

ring_control's own comment on their double-tap: "Limited by the ring's low
sample rate, so a natural fast double-tap may not register." Their timing
window is 60 ms to 1200 ms — they had to stretch the upper bound to 1.2
SECONDS, which makes it "two deliberate taps", not a double-tap.

At the 12 Hz the stock protocol allows, one sample is 83 ms, so a natural
200 ms double-tap is two or three samples apart and the spike itself may fall
entirely between samples. test_gestures.py measures exactly where this falls
over at 12 Hz versus the ~250 Hz firmware could do. That measurement is the
argument for flashing, and it is ours rather than inherited.
"""
from __future__ import annotations

import math
import statistics
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Literal

# Counts per g, from the prior art and the STK8321 datasheet's ±2g/12-bit mode.
# Only used for human-readable logging; nothing depends on it being exact,
# because the rest level is calibrated rather than assumed.
COUNTS_PER_G = 8192.0

GestureKind = Literal["tap", "double_tap", "triple_tap", "hold",
                      "music_enter", "music_volume", "music_exit"]


@dataclass(frozen=True)
class Sample:
    x: float
    y: float
    z: float
    t: float          # seconds, monotonic

    @property
    def mag(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)


@dataclass(frozen=True)
class Gesture:
    kind: GestureKind
    at: float
    #: for music_volume, the signed change in degrees since mode entry
    value: float | None = None
    #: hand orientation from BEFORE the gesture, when we could get it
    orientation: tuple[float, float, float] | None = None


@dataclass
class Config:
    # --- jolt detection ---
    #: |mag - rest| above this counts as a jolt. In counts; ~0.15g at 8192/g.
    jolt: float = 1200.0
    #: must fall back inside this band before another jolt can count
    release: float = 700.0
    #: a much tighter band, for deciding a reading is TRULY still
    still: float = 500.0

    # --- burst counting ---
    #: two jolts closer together than this are one tap seen twice
    min_gap: float = 0.05
    #: a burst ends after this much quiet; then we report how many taps it had
    burst_end: float = 0.35
    #: taps further apart than this start a new burst instead of extending one
    max_gap: float = 0.60
    #: ignore everything for this long after reporting, so a report cannot echo
    refractory: float = 0.40

    # --- hold ---
    #: sustained deviation for this long, with no second tap, is a hold
    hold_time: float = 0.90

    # --- calibration ---
    calibrate_n: int = 15
    #: how fast the rest value tracks drift, while quiet only
    rest_alpha: float = 0.02

    # --- orientation ---
    orientation_lead: float = 0.30
    orientation_max_age: float = 4.0

    # --- music mode ---
    #: double tap opens the window; it closes after this much no-input
    music_timeout: float = 5.0
    #: ignore roll smaller than this, so a resting hand does not drift the volume
    music_deadzone_deg: float = 8.0
    #: report a volume change only every this many degrees, to avoid a flood
    music_step_deg: float = 5.0
    #: which axis pair gives roll. UNVERIFIED until we have the ring on a hand —
    #: the ring's orientation on the finger decides this, and it is one line to
    #: change once measured.
    roll_axes: tuple[str, str] = ("y", "z")


def roll_degrees(s: Sample, axes: tuple[str, str]) -> float:
    """Wrist roll from the gravity vector.

    A 3-axis accelerometer at rest measures gravity, so the angle between two
    axes IS the orientation — no gyroscope needed. Only valid while the hand is
    not accelerating, which is why the caller gates this on stillness.
    """
    a = getattr(s, axes[0])
    b = getattr(s, axes[1])
    return math.degrees(math.atan2(a, b))


class Engine:
    """Feed samples, get gestures. Deterministic: same input, same output."""

    def __init__(self, on_gesture: Callable[[Gesture], None],
                 cfg: Config | None = None) -> None:
        self.cfg = cfg or Config()
        self.emit = on_gesture
        self.rest: float | None = None
        self._calib: list[float] = []
        self._armed = True
        self._burst: list[float] = []          # jolt times in the current burst
        self._last_report = -1e9
        self._still: deque[tuple[float, tuple[float, float, float]]] = deque()
        self._above_since: float | None = None  # for hold
        self._hold_fired = False
        # music mode
        self.music_until: float | None = None
        self._music_ref: float | None = None   # roll at entry
        self._music_last: float = 0.0          # last reported delta

    # ---- orientation -----------------------------------------------------
    def _orientation_before(self, when: float):
        """The pose from just before `when`, or None if nothing usable.

        Two exclusions, both from ring_control's hard-won experience: readings
        after the gesture began are a lie (mid-swing looks like gravity), and
        stale readings are worse than none (they describe where your hand was
        minutes ago, confidently and wrongly).
        """
        cutoff = when - self.cfg.orientation_lead
        usable = [(t, v) for t, v in self._still if t <= cutoff]
        if not usable:
            return None
        if when - usable[-1][0] > self.cfg.orientation_max_age:
            return None
        recent = [v for _, v in usable[-8:]]
        n = len(recent)
        return (sum(v[0] for v in recent) / n,
                sum(v[1] for v in recent) / n,
                sum(v[2] for v in recent) / n)

    # ---- main ------------------------------------------------------------
    def feed(self, s: Sample) -> None:
        mag = s.mag

        if self.rest is None:
            self._calib.append(mag)
            if len(self._calib) >= self.cfg.calibrate_n:
                self.rest = statistics.median(self._calib)
            return

        dev = abs(mag - self.rest)
        quiet = dev < self.cfg.release

        if quiet:
            # Track drift, but only while nothing is happening.
            self.rest += self.cfg.rest_alpha * (mag - self.rest)
            self._armed = True
            self._above_since = None
            self._hold_fired = False

        if dev < self.cfg.still:
            self._still.append((s.t, (s.x, s.y, s.z)))
            while self._still and s.t - self._still[0][0] > 15.0:
                self._still.popleft()

        # --- music mode owns the sample while it is open ---
        if self.music_until is not None:
            if self._music_tick(s, dev):
                return

        # --- hold: sustained deviation, not a tap ---
        if dev >= self.cfg.jolt:
            if self._above_since is None:
                self._above_since = s.t
            elif (not self._hold_fired
                  and s.t - self._above_since >= self.cfg.hold_time
                  and len(self._burst) <= 1):
                self._hold_fired = True
                self._report("hold", s.t, self._above_since)
                return

        # --- burst accounting ---
        if self._burst:
            gap = s.t - self._burst[-1]
            if gap > self.cfg.burst_end:
                self._close_burst(s.t)
            elif gap > self.cfg.max_gap:
                self._close_burst(s.t)

        if s.t - self._last_report < self.cfg.refractory:
            return
        if dev < self.cfg.jolt or not self._armed:
            return

        # A jolt. Hysteresis means we will not count again until it settles.
        self._armed = False
        if self._burst and s.t - self._burst[-1] < self.cfg.min_gap:
            return                      # same tap, seen twice
        self._burst.append(s.t)

    def _close_burst(self, now: float) -> None:
        n = len(self._burst)
        start = self._burst[0] if self._burst else now
        self._burst = []
        if n == 0 or self._hold_fired:
            return
        kind: GestureKind = "tap" if n == 1 else "double_tap" if n == 2 else "triple_tap"
        self._report(kind, now, start)
        if kind == "double_tap":
            self._music_open(now)

    def _report(self, kind: GestureKind, now: float, event_start: float) -> None:
        self._last_report = now
        self.emit(Gesture(kind=kind, at=now,
                          orientation=self._orientation_before(event_start)))

    # ---- music mode ------------------------------------------------------
    def _music_open(self, now: float) -> None:
        self.music_until = now + self.cfg.music_timeout
        self._music_ref = None
        self._music_last = 0.0
        self.emit(Gesture(kind="music_enter", at=now))

    def _music_tick(self, s: Sample, dev: float) -> bool:
        """Returns True if music mode consumed this sample."""
        assert self.music_until is not None
        if s.t > self.music_until:
            self.music_until = None
            self.emit(Gesture(kind="music_exit", at=s.t))
            return False

        # Roll is only meaningful while the hand is not being accelerated —
        # atan2 on a shaking hand measures the shake, not the pose.
        if dev >= self.cfg.still:
            return False

        roll = roll_degrees(s, self.cfg.roll_axes)
        if self._music_ref is None:
            self._music_ref = roll
            return True

        delta = roll - self._music_ref
        # Unwrap: rolling past +/-180 should not read as a 360-degree jump.
        while delta > 180:
            delta -= 360
        while delta < -180:
            delta += 360

        if abs(delta) < self.cfg.music_deadzone_deg:
            return True
        if abs(delta - self._music_last) < self.cfg.music_step_deg:
            return True

        self._music_last = delta
        # Any real input keeps the window open.
        self.music_until = s.t + self.cfg.music_timeout
        self.emit(Gesture(kind="music_volume", at=s.t, value=round(delta, 1)))
        return True

    def tick(self, now: float) -> None:
        """Call when samples stop arriving, so a trailing burst still closes."""
        if self._burst and now - self._burst[-1] > self.cfg.burst_end:
            self._close_burst(now)
        if self.music_until is not None and now > self.music_until:
            self.music_until = None
            self.emit(Gesture(kind="music_exit", at=now))
