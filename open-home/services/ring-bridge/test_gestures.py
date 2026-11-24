#!/usr/bin/env python3
"""
Gesture engine tests, against synthetic accelerometer traces.

No ring required. The point is twofold: prove the state machine does what it
claims, and MEASURE the sample-rate question rather than quoting someone else's
opinion about it.

    ./.venv/bin/python test_gestures.py
"""
from __future__ import annotations

import math

from gestures import COUNTS_PER_G, Config, Engine, Gesture, Sample

G = COUNTS_PER_G


def trace(duration: float, hz: float, taps: list[float],
          spike: float = 4000.0, spike_width: float = 0.030,
          roll_ramp: tuple[float, float, float] | None = None) -> list[Sample]:
    """Build a sample trace.

    `taps` are the times of tap PEAKS. Each tap is a short burst of extra
    acceleration of width `spike_width` — which is the crux of the whole
    sample-rate question: a tap is a ~30 ms transient, and at 12 Hz the gap
    between samples is 83 ms, so the spike can land entirely between two
    samples and simply not exist as far as the detector is concerned.

    `roll_ramp` is (start_t, end_t, degrees) — rotates the gravity vector in
    the y/z plane so roll-to-volume can be exercised.
    """
    out: list[Sample] = []
    n = int(duration * hz)
    for i in range(n):
        t = i / hz
        # Gravity along +z at rest, a little sensor noise.
        ang = 0.0
        if roll_ramp:
            s0, s1, deg = roll_ramp
            if t >= s1:
                ang = deg
            elif t > s0:
                ang = deg * (t - s0) / (s1 - s0)
        rad = math.radians(ang)
        x = 0.0
        y = G * math.sin(rad)
        z = G * math.cos(rad)
        extra = 0.0
        for tp in taps:
            if abs(t - tp) <= spike_width / 2:
                extra = spike
        # Add the tap along z so it shows up in magnitude.
        z += extra
        out.append(Sample(x=x, y=y, z=z, t=t))
    return out


def run(samples: list[Sample], cfg: Config | None = None) -> list[Gesture]:
    got: list[Gesture] = []
    e = Engine(got.append, cfg)
    for s in samples:
        e.feed(s)
    e.tick(samples[-1].t + 1.0)
    return got


def kinds(gs: list[Gesture]) -> list[str]:
    return [g.kind for g in gs]


# ---------------------------------------------------------------- tests ----
def test_still_is_silent():
    gs = run(trace(5.0, 250, taps=[]))
    assert gs == [], f"a still hand produced {kinds(gs)}"
    return "still hand -> nothing"


def test_single_tap():
    gs = run(trace(4.0, 250, taps=[2.0]))
    assert kinds(gs) == ["tap"], kinds(gs)
    return "one tap -> tap"


def test_double_tap_at_250hz():
    gs = run(trace(4.0, 250, taps=[2.0, 2.20]))
    assert "double_tap" in kinds(gs), kinds(gs)
    assert "music_enter" in kinds(gs), "double tap should open music mode"
    return "double tap @250Hz -> double_tap + music_enter"


def test_triple_tap():
    gs = run(trace(4.0, 250, taps=[2.0, 2.18, 2.36]))
    assert "triple_tap" in kinds(gs), kinds(gs)
    assert "music_enter" not in kinds(gs), "triple must NOT open music mode"
    return "triple tap -> triple_tap, no music mode"


def test_one_tap_is_not_two():
    """Hysteresis. Without the release band a single 30 ms spike sampled at
    250 Hz spans ~7 samples and reads as seven taps."""
    gs = run(trace(4.0, 250, taps=[2.0], spike_width=0.040))
    assert kinds(gs) == ["tap"], f"hysteresis failed: {kinds(gs)}"
    return "wide single spike -> still one tap"


def test_hold():
    # A long sustained deviation rather than a transient.
    samples = []
    for i in range(int(4.0 * 250)):
        t = i / 250
        extra = 4000.0 if 1.0 <= t <= 2.5 else 0.0
        samples.append(Sample(0.0, 0.0, G + extra, t))
    gs = run(samples)
    assert "hold" in kinds(gs), kinds(gs)
    return "sustained press -> hold"


def test_music_roll_changes_volume():
    # Double tap, then rotate the hand 40 degrees over a second.
    samples = trace(6.0, 250, taps=[1.0, 1.20],
                    roll_ramp=(1.8, 2.8, 40.0))
    gs = run(samples)
    k = kinds(gs)
    assert "music_enter" in k, k
    vols = [g for g in gs if g.kind == "music_volume"]
    assert vols, f"no volume events: {k}"
    assert vols[-1].value is not None and vols[-1].value > 25, \
        f"expected a large roll delta, got {vols[-1].value}"
    return (f"roll 40deg in music mode -> {len(vols)} volume events, "
            f"last delta {vols[-1].value}deg")


def test_music_mode_times_out():
    samples = trace(9.0, 250, taps=[1.0, 1.20])
    gs = run(samples)
    assert "music_exit" in kinds(gs), kinds(gs)
    return "music mode exits on idle"


def test_roll_outside_music_mode_does_nothing():
    """The whole reason the mode is modal: a hand rotates all day."""
    samples = trace(6.0, 250, taps=[], roll_ramp=(1.0, 3.0, 70.0))
    gs = run(samples)
    assert gs == [], f"roll without a wake gesture emitted {kinds(gs)}"
    return "roll with no wake gesture -> nothing"


# ------------------------------------------------- the rate measurement ----
def measure_rate_vs_gap():
    """At what sample rate does a natural double-tap survive?

    This is the firmware argument, measured. 12 Hz is what the stock protocol's
    `a1 03` polling achieves; ~250 Hz is what firmware on the MCU could do.
    """
    rates = [12, 25, 50, 125, 250]
    # Only gaps a human actually produces when double-tapping, and all of them
    # inside Config.burst_end. Earlier this swept out to 500 ms and the table
    # showed misses at every rate — which looked like a detector bug and is
    # not: two taps 500 ms apart ARE two separate taps, by the configured
    # definition. Measuring behaviour we deliberately designed against, and
    # printing it as failure, is how you end up chasing a bug that isn't there.
    cfg = Config()
    gaps = [0.10, 0.15, 0.20, 0.25, 0.30]
    assert max(gaps) < cfg.burst_end, "gaps must be inside the burst window"
    print("\n  double-tap detection, by sample rate and inter-tap gap")
    print(f"  (tap = 30 ms transient; burst window = {cfg.burst_end*1000:.0f} ms;")
    print("   8 phase offsets per cell, since whether a transient lands on a")
    print("   sample is luck at low rates; 'D' = detected in most trials)\n")
    header = "        gap:" + "".join(f"{int(g*1000):>7}ms" for g in gaps)
    print(header)
    results: dict[int, int] = {}
    for hz in rates:
        row = f"  {hz:>5} Hz:  "
        hits = 0
        for gap in gaps:
            # Average over several phase offsets: whether a 30 ms spike lands
            # on a sample is luck at low rates, so testing one alignment would
            # flatter or damn it unfairly.
            detected = 0
            trials = 8
            for p in range(trials):
                offset = (p / trials) / hz
                samples = trace(4.0, hz, taps=[2.0 + offset, 2.0 + offset + gap])
                if "double_tap" in kinds(run(samples)):
                    detected += 1
            ok = detected >= trials // 2
            hits += 1 if ok else 0
            row += f"{('D' if ok else '.')+f'({detected}/{trials})':>9}"
        results[hz] = hits
        print(row)
    print()
    return results


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    print("gesture engine tests\n")
    for fn in tests:
        try:
            msg = fn()
            print(f"   ok   {msg}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {fn.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"  ERR   {fn.__name__}: {type(e).__name__}: {e}")

    res = measure_rate_vs_gap()
    print(f"  {len(tests) - failed}/{len(tests)} tests passed")
    if res:
        worst = min(res, key=lambda h: res[h])
        best = max(res, key=lambda h: res[h])
        print(f"  {worst} Hz detected {res[worst]}/5 gap values; "
              f"{best} Hz detected {res[best]}/5")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
