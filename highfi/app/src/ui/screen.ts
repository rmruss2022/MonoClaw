// A screen builds its DOM once and exposes an update(state) hook. main.ts calls
// update on every store change while the screen is active, so we get live data
// without tearing down inputs (sliders keep their drag/focus).

import type { AppState } from "../state.ts";

export interface Screen {
  /** Root element mounted into the screen container. */
  el: HTMLElement;
  /** Reconcile the DOM with the latest store state. */
  update(state: AppState): void;
  /** Called when the tab becomes active. */
  onEnter?(): void;
  /** Called when leaving the tab. */
  onLeave?(): void;
}
