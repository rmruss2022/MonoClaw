import type { Screen } from "../ui/screen.ts";
import type { AppState } from "../state.ts";
import { el, icon } from "../ui/dom.ts";
import { getConnection } from "../connectionManager.ts";
import { VAPE_LIMITS, type VapeFault, type VapeMode } from "../protocol.ts";

const FAULT_TEXT: Record<VapeFault, string> = {
  locked: "Locked — unlock to enable fire",
  "no-cart": "No cart detected — screw in a 510 cartridge",
  short: "Short circuit — coil resistance too low",
  "over-temp": "Cooling — coil over temperature",
  cooling: "Cooling down after 10 s cutoff",
};

export function createVape(): Screen {
  const conn = () => getConnection();

  // --- battery ---
  const battPct = el("span", { class: "batt-pct" }, "—");
  const battFill = el("div", { class: "batt-fill" });
  const battSub = el("span", { class: "batt-sub" }, "");
  const battery = el("div", { class: "vape-battery" }, [
    el("div", { class: "batt-ring" }, [battFill, battPct]),
    battSub,
  ]);

  // --- coil status ---
  const coilPresent = statLine("Cartridge", "—");
  const coilOhms = statLine("Resistance", "—");
  const coilTemp = statLine("Coil temp", "—");
  const coilCard = el("div", { class: "card coil-card" }, [
    el("h2", { class: "card-title" }, [icon("🧩"), "Coil status"]),
    coilPresent.row,
    coilOhms.row,
    coilTemp.row,
  ]);

  // --- setpoint ---
  const modeVolts = el("button", { class: "seg" }, "Voltage");
  const modeWatts = el("button", { class: "seg" }, "Watts");
  modeVolts.addEventListener("click", () => setMode("voltage"));
  modeWatts.addEventListener("click", () => setMode("watts"));

  const setValue = el("span", { class: "set-value" }, "—");
  let adjusting = false;
  const slider = el("input", {
    class: "set-slider",
    type: "range",
    step: 0.1,
    "aria-label": "Setpoint",
  }) as HTMLInputElement;
  const setRange = el("div", { class: "set-range" });

  slider.addEventListener("input", () => {
    adjusting = true;
    updateSetLabel(Number(slider.value), currentMode);
  });
  slider.addEventListener("change", () => {
    const val = Number(slider.value);
    if (currentMode === "watts") conn().vapeSet({ mode: "watts", watts: val });
    else conn().vapeSet({ mode: "voltage", volts: val });
    adjusting = false;
  });

  const setpointCard = el("div", { class: "card set-card" }, [
    el("h2", { class: "card-title" }, [icon("🎚"), "Setpoint"]),
    el("div", { class: "seg-group" }, [modeVolts, modeWatts]),
    el("div", { class: "set-readout" }, [setValue]),
    slider,
    setRange,
    el("p", { class: "hint" }, "Clamped to the firmware-safe range."),
  ]);

  // --- fire ---
  const fireTimer = el("span", { class: "fire-timer" }, "0.0s");
  const fireLabel = el("span", { class: "fire-label" }, "HOLD TO FIRE");
  const fireBtn = el(
    "button",
    { class: "fire-btn", "aria-label": "Hold to fire" },
    [fireLabel, fireTimer],
  );
  const fireProgress = el("div", { class: "fire-progress" });
  fireBtn.append(fireProgress);

  const startFire = (e: Event) => {
    e.preventDefault();
    if (fireBtn.classList.contains("disabled")) return;
    conn().vapeFire(true);
  };
  const stopFire = () => conn().vapeFire(false);
  fireBtn.addEventListener("pointerdown", startFire);
  fireBtn.addEventListener("pointerup", stopFire);
  fireBtn.addEventListener("pointerleave", stopFire);
  fireBtn.addEventListener("pointercancel", stopFire);

  const faultBanner = el("div", { class: "fault-banner hidden" });

  // --- lock ---
  const lockBtn = el("button", { class: "btn lock-btn" }, "Unlock");
  lockBtn.addEventListener("click", () => {
    conn().vapeLock(!lastLocked);
  });

  const root = el("section", { class: "screen vape" }, [
    el("div", { class: "safety-strip" }, [
      icon("⚠"),
      el(
        "span",
        {},
        "Heating element + Li-ion. Every fire path is interlocked in firmware.",
      ),
    ]),
    battery,
    faultBanner,
    coilCard,
    setpointCard,
    el("div", { class: "fire-zone" }, [fireBtn]),
    lockBtn,
  ]);

  let currentMode: VapeMode = "voltage";
  let lastLocked = true;

  function setMode(mode: VapeMode): void {
    if (mode === "watts") {
      conn().vapeSet({ mode: "watts", watts: Number(slider.value) || 9 });
    } else {
      conn().vapeSet({ mode: "voltage", volts: Number(slider.value) || 3.2 });
    }
  }

  function updateSetLabel(val: number, mode: VapeMode): void {
    setValue.textContent =
      mode === "watts" ? `${val.toFixed(1)} W` : `${val.toFixed(1)} V`;
  }

  function applyModeUi(mode: VapeMode): void {
    currentMode = mode;
    modeWatts.classList.toggle("active", mode === "watts");
    modeVolts.classList.toggle("active", mode === "voltage");
    const lim = mode === "watts" ? VAPE_LIMITS.watts : VAPE_LIMITS.volts;
    slider.min = String(lim.min);
    slider.max = String(lim.max);
    slider.step = mode === "watts" ? "0.5" : "0.1";
    setRange.replaceChildren(
      el("span", {}, mode === "watts" ? `${lim.min} W` : `${lim.min} V`),
      el("span", {}, mode === "watts" ? `${lim.max} W` : `${lim.max} V`),
    );
  }

  return {
    el: root,
    onLeave() {
      // Never leave the coil energized when navigating away.
      conn().vapeFire(false);
    },
    update(state: AppState) {
      const v = state.device?.vape;
      const p = state.device?.power;
      if (!v || !p) return;

      // battery
      battPct.textContent = `${Math.round(p.battPct)}%`;
      battFill.style.height = `${Math.round(p.battPct)}%`;
      battFill.classList.toggle("low", p.battPct <= 15);
      battSub.textContent = p.charging
        ? `Charging · ${p.voltage.toFixed(2)} V`
        : `${p.voltage.toFixed(2)} V`;

      // coil
      coilPresent.value.textContent = v.cartPresent ? "Present" : "None";
      coilPresent.value.classList.toggle("bad", !v.cartPresent);
      coilOhms.value.textContent = v.cartPresent
        ? `${v.coilOhms.toFixed(2)} Ω`
        : "—";
      coilTemp.value.textContent = `${Math.round(v.coilTempC)} °C`;
      coilTemp.value.classList.toggle(
        "warn",
        v.coilTempC >= VAPE_LIMITS.overTempC * 0.8,
      );

      // setpoint (don't fight the user's drag)
      if (!adjusting) {
        applyModeUi(v.mode);
        const val = v.mode === "watts" ? v.setWatts : v.setVolts;
        slider.value = String(val);
        updateSetLabel(val, v.mode);
      }

      // lock
      lastLocked = v.locked;
      lockBtn.textContent = v.locked ? "Unlock" : "Lock";
      lockBtn.classList.toggle("locked", v.locked);

      // fault + fire enablement
      const fault: VapeFault | null = v.fault ?? null;
      if (fault) {
        faultBanner.classList.remove("hidden");
        faultBanner.replaceChildren(icon("🔒"), FAULT_TEXT[fault]);
      } else {
        faultBanner.classList.add("hidden");
      }

      const canFire = !fault;
      fireBtn.classList.toggle("disabled", !canFire);
      fireBtn.classList.toggle("firing", v.firing);
      fireLabel.textContent = v.firing
        ? "FIRING"
        : canFire
          ? "HOLD TO FIRE"
          : "LOCKED";

      fireTimer.textContent = `${v.sessionS.toFixed(1)}s`;
      const frac = Math.min(1, v.sessionS / VAPE_LIMITS.maxSessionS);
      fireProgress.style.width = `${frac * 100}%`;
      fireProgress.classList.toggle("hot", frac > 0.7);
    },
  };
}

function statLine(label: string, value: string) {
  const valueEl = el("span", { class: "stat-value" }, value);
  const row = el("div", { class: "stat-row" }, [
    el("span", { class: "stat-label" }, label),
    valueEl,
  ]);
  return { row, value: valueEl };
}
