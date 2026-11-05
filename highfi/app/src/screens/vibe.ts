import type { Screen } from "../ui/screen.ts";
import type { AppState } from "../state.ts";
import { el } from "../ui/dom.ts";
import { getConnection } from "../connectionManager.ts";

interface LedPresetDef {
  id: string;
  label: string;
  swatch: string;
}

const LED_PRESETS: LedPresetDef[] = [
  { id: "sunset", label: "Sunset", swatch: "linear-gradient(135deg,#ff8a3d,#ff3d77)" },
  { id: "amber", label: "Amber", swatch: "linear-gradient(135deg,#ffb347,#ff7b00)" },
  { id: "grape", label: "Grape", swatch: "linear-gradient(135deg,#a24bff,#5b2bd6)" },
  { id: "mint", label: "Mint", swatch: "linear-gradient(135deg,#4bffb3,#00c2a8)" },
  { id: "ocean", label: "Ocean", swatch: "linear-gradient(135deg,#3db2ff,#5b2bd6)" },
  { id: "ember", label: "Ember", swatch: "linear-gradient(135deg,#ff5f3d,#b31217)" },
  { id: "aurora", label: "Aurora", swatch: "linear-gradient(135deg,#5bffcf,#a24bff)" },
  { id: "off", label: "Off", swatch: "linear-gradient(135deg,#2a2440,#1a1626)" },
];

const EQ_PRESETS = ["Flat", "Warm", "Bass Boost", "Vocal", "Late Night", "Party"];

export function createVibe(): Screen {
  const conn = () => getConnection();

  let ledSel = "sunset";
  let eqSel = "Flat";

  const ledGrid = el("div", { class: "led-grid" });
  for (const p of LED_PRESETS) {
    const swatch = el("span", { class: "led-swatch", style: `background:${p.swatch}` });
    const btn = el(
      "button",
      {
        class: "led-tile",
        "data-id": p.id,
        onclick: () => {
          ledSel = p.id;
          conn().led(p.id);
          syncLed();
        },
      },
      [swatch, el("span", { class: "led-label" }, p.label)],
    );
    ledGrid.append(btn);
  }

  const eqGrid = el("div", { class: "eq-grid" });
  for (const name of EQ_PRESETS) {
    const btn = el(
      "button",
      {
        class: "eq-tile",
        "data-id": name,
        onclick: () => {
          eqSel = name;
          conn().eq(name);
          syncEq();
        },
      },
      name,
    );
    eqGrid.append(btn);
  }

  function syncLed(): void {
    for (const child of Array.from(ledGrid.children)) {
      child.classList.toggle(
        "active",
        (child as HTMLElement).dataset.id === ledSel,
      );
    }
  }
  function syncEq(): void {
    for (const child of Array.from(eqGrid.children)) {
      child.classList.toggle(
        "active",
        (child as HTMLElement).dataset.id === eqSel,
      );
    }
  }

  const root = el("section", { class: "screen vibe" }, [
    el("h1", { class: "screen-title" }, "Vibe"),
    el("div", { class: "card" }, [
      el("h2", { class: "card-title" }, "LED preset"),
      el("p", { class: "hint" }, "Sets the WS2812 status ring / glow."),
      ledGrid,
    ]),
    el("div", { class: "card" }, [
      el("h2", { class: "card-title" }, "EQ preset"),
      el("p", { class: "hint" }, "Shapes the onboard speaker output."),
      eqGrid,
    ]),
  ]);

  syncLed();
  syncEq();

  return {
    el: root,
    update(_state: AppState) {
      // LED/EQ presets are fire-and-forget commands; no device-side mirror in
      // the protocol, so selection is tracked locally.
    },
  };
}
