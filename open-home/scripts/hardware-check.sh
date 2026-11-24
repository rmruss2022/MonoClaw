#!/usr/bin/env bash
#
# Is this box enough to run openhome?
#
# Specs on a page are guesses. This measures the four things that have actually
# been bottlenecks on real hardware, then says yes, yes-but, or no.
#
# Every threshold in here came from a measurement, and the comment next to it
# says which. When a new one bites, add it here rather than to a wiki page.
#
#   ./hardware-check.sh            # full check
#   ./hardware-check.sh --json     # machine-readable, for an installer
#
set -uo pipefail

JSON=0
[ "${1:-}" = "--json" ] && JSON=1

PASS=0; WARN=0; FAIL=0
declare -a ROWS

say() { [ "$JSON" = 1 ] || printf '%b\n' "$1"; }
row() { # name verdict value note
  ROWS+=("{\"check\":\"$1\",\"verdict\":\"$2\",\"value\":\"$3\",\"note\":\"$4\"}")
  case "$2" in
    pass) PASS=$((PASS+1)); [ "$JSON" = 1 ] || printf '  \033[32m ok \033[0m %-22s %-22s %s\n' "$1" "$3" "$4" ;;
    warn) WARN=$((WARN+1)); [ "$JSON" = 1 ] || printf '  \033[33mwarn\033[0m %-22s %-22s %s\n' "$1" "$3" "$4" ;;
    fail) FAIL=$((FAIL+1)); [ "$JSON" = 1 ] || printf '  \033[31mFAIL\033[0m %-22s %-22s %s\n' "$1" "$3" "$4" ;;
    *)                      [ "$JSON" = 1 ] || printf '       %-22s %-22s %s\n' "$1" "$3" "$4" ;;
  esac
}

# ---------- what is this thing ----------
OS=$(uname -s)
ARCH=$(uname -m)
if [ -r /proc/device-tree/model ]; then
  MODEL=$(tr -d '\0' < /proc/device-tree/model)
elif [ "$OS" = Darwin ]; then
  MODEL=$(sysctl -n hw.model 2>/dev/null || echo "Mac")
else
  MODEL=$(cat /sys/devices/virtual/dmi/id/product_name 2>/dev/null || echo unknown)
fi

if [ "$OS" = Darwin ]; then
  CORES=$(sysctl -n hw.ncpu)
  RAM_MB=$(( $(sysctl -n hw.memsize) / 1048576 ))
else
  CORES=$(nproc 2>/dev/null || grep -c ^processor /proc/cpuinfo)
  RAM_MB=$(( $(awk '/MemTotal/{print $2}' /proc/meminfo) / 1024 ))
fi
DISK_FREE_GB=$(df -k / | awk 'NR==2{printf "%d", $4/1048576}')

say "\n\033[1mopenhome hardware check\033[0m"
say "  $MODEL — $OS/$ARCH, ${CORES} cores, ${RAM_MB} MB RAM, ${DISK_FREE_GB} GB free\n"

# ---------- 1. RAM ----------
#
# Measured on the reference box — a 2 GB Pi 4 (1843 MB usable) after 36 hours
# of continuous uptime, everything running:
#
#   voice client (python + onnxruntime + openWakeWord)   233 MB RSS
#   soloist (Spotify Connect, two processes)               94 MB
#   hub (node --experimental-strip-types)                 134 MB
#   PipeWire + WirePlumber + pulse shim                    46 MB
#   ---------------------------------------------------------------
#   openhome itself                                       506 MB
#   whole system, including the OS                        625 MB used
#   swap used                                               0 MB
#
# So: 1 GB is too tight once a TypeScript recompile spikes on restart, 2 GB has
# 1.2 GB headroom and has never touched swap, and 4 GB only matters if you add
# local speech-to-text — the one feature that moves this by an order of
# magnitude. Everything else here is rounding error.
if   [ "$RAM_MB" -lt 1500 ]; then row "RAM" fail "${RAM_MB} MB" "need 2 GB; measured 506 MB app + 120 MB OS, plus build spikes"
elif [ "$RAM_MB" -lt 3000 ]; then row "RAM" warn "${RAM_MB} MB" "fine — reference box uses 625 MB of 1843, no swap"
else                               row "RAM" pass "${RAM_MB} MB" "comfortable"
fi

# ---------- 2. Cores ----------
#
# The wake word is the floor, and it is relentless rather than heavy: measured
# 19.3 ms of inference per 80 ms frame on a Pi 4 at 1.5 GHz = 24% of one core,
# forever, whether or not anyone is talking.
#
# That has to coexist with: the hub answering HTTP, mpv decoding an mp3 to a
# Bluetooth sink, and PipeWire. Two cores is the minimum that does not make the
# voice stutter; the reference Pi has four and sits at ~35% total.
if   [ "$CORES" -lt 2 ]; then row "CPU cores" fail "$CORES" "wake word alone is 24% of a core, continuously"
elif [ "$CORES" -lt 4 ]; then row "CPU cores" warn "$CORES" "works; 4 leaves room for playback + HTTP"
else                          row "CPU cores" pass "$CORES" ""
fi

# ---------- 3. Single-core speed ----------
#
# Not total throughput — single-core speed, because the wake word is one
# ONNX session on one thread and cannot be spread. This busy-loop is crude but
# it correlates: the reference Pi 4 (throttled to 1.5 GHz) scores ~1.0 by
# construction, and anything materially slower will drop audio frames.
say "\n  measuring single-core speed (3s)..."
T0=$(date +%s%N)
ITER=$(python3 - <<'PY' 2>/dev/null || echo 0
# Count BLOCKS, not the accumulator. The first version of this printed `n` —
# the modular value — which is a pseudo-random number in [0, 1000003) and has
# nothing to do with speed. Three runs on the same idle box gave 75357, 999993
# and 27941, and it still produced a confident "0.75x" verdict. A benchmark
# that cannot be checked against itself is worse than no benchmark.
import time
blocks = 0; n = 0; t = time.time()
while time.time() - t < 3.0:
    for _ in range(1000):
        n = (n * 31 + 7) % 1000003
    blocks += 1
print(blocks)
PY
)
T1=$(date +%s%N)
MS=$(( (T1-T0)/1000000 ))
# The reference Pi 4 scores 6625 / 6626 / 6738 (+/-1.7%) — and it is THROTTLED
# to 1500 MHz when it does, which is its normal operating state. Calibrating
# against the throttled number rather than the rated 2000 MHz means 1.00x is
# "known to run the wake word without dropping frames", not an aspiration.
PI4_BASELINE=6600
SCORE=$(python3 -c "print(f'{${ITER:-0}/$PI4_BASELINE:.2f}')" 2>/dev/null || echo 0)
if   python3 -c "import sys; sys.exit(0 if $SCORE >= 0.9 else 1)" 2>/dev/null; then
  row "single-core speed" pass "${SCORE}x Pi 4" "wake word needs ~0.9x"
elif python3 -c "import sys; sys.exit(0 if $SCORE >= 0.6 else 1)" 2>/dev/null; then
  row "single-core speed" warn "${SCORE}x Pi 4" "wake word may drop frames under load"
else
  row "single-core speed" fail "${SCORE}x Pi 4" "too slow for continuous wake-word inference"
fi

# ---------- 4. Storage: free space AND speed ----------
#
# Measured on the reference box, 58 GB card, 7.5 GB used in total:
#   repo checkout (whole monorepo)   1.2 GB   <- only open-home is needed: 557 MB
#   voice venv (onnxruntime is most of it)  302 MB
#   OS + journald + everything else   ~6 GB
#   spoken-reply cache                240 KB  (capped by phrase length)
#
# 16 GB is comfortable. 8 GB works if you clone shallow and cap journald. The
# number people expect to matter here does not.
#
# SPEED is the constraint, and it is the one that kills these boxes: this
# reference Pi corrupted its SD card once already. Random writes on a cheap
# card are what make a hub feel broken.
if   [ "$DISK_FREE_GB" -lt 4 ];  then row "disk free" fail "${DISK_FREE_GB} GB" "need ~4 GB; install is ~1 GB + OS"
elif [ "$DISK_FREE_GB" -lt 10 ]; then row "disk free" warn "${DISK_FREE_GB} GB" "fine, but journald will fill it"
else                                  row "disk free" pass "${DISK_FREE_GB} GB" ""
fi

say "  measuring disk write (64 MB)..."
TMP=$(mktemp -t ohcheck.XXXXXX)
DD=$( { dd if=/dev/zero of="$TMP" bs=1m count=64 2>&1 || dd if=/dev/zero of="$TMP" bs=1M count=64 2>&1; } | tail -1 )
rm -f "$TMP"
# The two dd dialects report different UNITS, and conflating them is how this
# first reported 9,479,992,089 MB/s on a Mac:
#   GNU   : "67108864 bytes (67 MB, 64 MiB) copied, 0.2 s, 335 MB/s"
#   BSD   : "67108864 bytes transferred in 0.007 secs (9479992089 bytes/sec)"
# A reading that absurd is harmless because you notice it; one that is wrong by
# 10x is not, so parse the unit rather than the first number that matches.
MBS=$(printf '%s' "$DD" | grep -oE '[0-9.]+ MB/s' | head -1 | grep -oE '^[0-9.]+')
if [ -z "${MBS:-}" ]; then
  BPS=$(printf '%s' "$DD" | grep -oE '\([0-9]+ bytes/sec\)' | grep -oE '[0-9]+')
  [ -n "${BPS:-}" ] && MBS=$(python3 -c "print(f'{$BPS/1048576:.0f}')" 2>/dev/null)
fi
if [ -z "${MBS:-}" ]; then
  row "disk write" info "unknown" "could not parse dd output"
elif python3 -c "import sys; sys.exit(0 if ${MBS} >= 30 else 1)" 2>/dev/null; then
  row "disk write" pass "${MBS} MB/s" ""
elif python3 -c "import sys; sys.exit(0 if ${MBS} >= 10 else 1)" 2>/dev/null; then
  row "disk write" warn "${MBS} MB/s" "slow card — a known cause of corruption here"
else
  row "disk write" fail "${MBS} MB/s" "too slow; use a better card or an SSD"
fi

# ---------- 5. Runtime prerequisites ----------
NODE=$(node -v 2>/dev/null || echo "")
if [ -z "$NODE" ]; then
  row "node" fail "missing" "hub runs on node >= 22 (--experimental-strip-types)"
else
  NMAJ=$(printf '%s' "$NODE" | sed 's/^v//' | cut -d. -f1)
  if [ "$NMAJ" -ge 22 ]; then row "node" pass "$NODE" ""
  else row "node" fail "$NODE" "need >= 22 for --experimental-strip-types"; fi
fi

PY=$(python3 -V 2>&1 | awk '{print $2}')
if [ -z "$PY" ]; then
  row "python3" fail "missing" "voice client needs 3.11+"
else
  # 3.13 has no tflite-runtime wheel for aarch64, which is why the voice client
  # pins openWakeWord 0.4.0 (ONNX-only). Worth saying out loud at install time.
  case "$PY" in
    # 3.13 has no tflite-runtime wheel for aarch64, which is why the voice
    # client pins openWakeWord 0.4.0 (ONNX-only). Only say so on 3.13+, or the
    # note reads as a warning about a version you are not running.
    3.1[3-9]*|3.[2-9]*) row "python3" pass "$PY" "no tflite wheel at 3.13+ — needs openWakeWord 0.4.x (ONNX)" ;;
    3.1[12]*)           row "python3" pass "$PY" "" ;;
    *) row "python3" fail "$PY" "need 3.11+" ;;
  esac
fi

for bin in mpv aplay wpctl pw-dump; do
  if command -v "$bin" >/dev/null 2>&1; then row "$bin" pass "present" ""
  else row "$bin" warn "missing" "needed for audio out / ducking"; fi
done

# ---------- 6. Thermals, on the boards that report them ----------
#
# This is not a spec-sheet item and it should be. The reference Pi spent a whole
# evening at 76 C with throttled=0x80000 — bit 19, soft temperature limit — which
# drops it from 2.0 GHz to 1.5 GHz. Nothing errors; the voice just gets slower,
# which is indistinguishable from a software problem and cost hours of
# misdirected debugging.
if command -v vcgencmd >/dev/null 2>&1; then
  TEMP=$(vcgencmd measure_temp 2>/dev/null | grep -oE '[0-9.]+')
  THR=$(vcgencmd get_throttled 2>/dev/null | cut -d= -f2)
  if [ -n "${TEMP:-}" ]; then
    if python3 -c "import sys; sys.exit(0 if ${TEMP} < 60 else 1)" 2>/dev/null; then
      row "temperature" pass "${TEMP} C" ""
    elif python3 -c "import sys; sys.exit(0 if ${TEMP} < 75 else 1)" 2>/dev/null; then
      row "temperature" warn "${TEMP} C" "throttles at 60 C — fit a heatsink"
    else
      row "temperature" fail "${TEMP} C" "throttling hard; heatsink required"
    fi
  fi
  case "${THR:-0x0}" in
    0x0) row "throttling" pass "none" "" ;;
    *8000*|*80000*) row "throttling" warn "$THR" "soft temp limit reached — running below rated clock" ;;
    *1|*2|*4) row "throttling" fail "$THR" "UNDERVOLTAGE — bad PSU or cable, corrupts storage" ;;
    *) row "throttling" warn "$THR" "see 'vcgencmd get_throttled' bit meanings" ;;
  esac
fi

# ---------- verdict ----------
if [ "$JSON" = 1 ]; then
  printf '{"model":"%s","os":"%s","arch":"%s","cores":%s,"ramMB":%s,"diskFreeGB":%s,"score":%s,"pass":%s,"warn":%s,"fail":%s,"checks":[%s]}\n' \
    "$MODEL" "$OS" "$ARCH" "$CORES" "$RAM_MB" "$DISK_FREE_GB" "${SCORE:-0}" "$PASS" "$WARN" "$FAIL" \
    "$(IFS=,; echo "${ROWS[*]}")"
  exit 0
fi

say ""
if [ "$FAIL" -gt 0 ]; then
  say "\033[31mNot supported\033[0m — $FAIL blocking, $WARN warnings. See the FAIL rows."
  exit 2
elif [ "$WARN" -gt 0 ]; then
  say "\033[33mSupported, with caveats\033[0m — $WARN warnings. It will run; read them."
  exit 1
else
  say "\033[32mSupported\033[0m — $PASS checks passed."
  exit 0
fi
