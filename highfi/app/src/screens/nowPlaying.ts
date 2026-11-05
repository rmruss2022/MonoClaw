import type { Screen } from "../ui/screen.ts";
import type { AppState } from "../state.ts";
import { el, icon } from "../ui/dom.ts";
import { mmss } from "../ui/format.ts";
import { getConnection } from "../connectionManager.ts";
import type { RepeatMode } from "../protocol.ts";

export function createNowPlaying(): Screen {
  const conn = () => getConnection();

  const art = el("div", { class: "np-art" }, [
    el("div", { class: "np-art-glow" }),
    el("span", { class: "np-art-mark" }, "hi-fi"),
  ]);
  const title = el("h1", { class: "np-title" }, "—");
  const artist = el("p", { class: "np-artist" }, "—");

  // scrubber
  let seeking = false;
  const scrub = el("input", {
    class: "scrubber",
    type: "range",
    min: 0,
    max: 100,
    value: 0,
    "aria-label": "Seek",
  }) as HTMLInputElement;
  const curTime = el("span", { class: "time" }, "0:00");
  const durTime = el("span", { class: "time" }, "0:00");
  scrub.addEventListener("input", () => {
    seeking = true;
    curTime.textContent = mmss(Number(scrub.value));
  });
  scrub.addEventListener("change", () => {
    conn().seek(Number(scrub.value));
    seeking = false;
  });

  // transport
  const btnPrev = el(
    "button",
    { class: "tbtn", "aria-label": "Previous", onclick: () => conn().prev() },
    icon("⏮"),
  );
  const btnPlay = el(
    "button",
    { class: "tbtn tbtn-primary", "aria-label": "Play/Pause" },
    icon("▶"),
  );
  const btnNext = el(
    "button",
    { class: "tbtn", "aria-label": "Next", onclick: () => conn().next() },
    icon("⏭"),
  );

  // volume
  let adjustingVol = false;
  const vol = el("input", {
    class: "volume",
    type: "range",
    min: 0,
    max: 100,
    value: 60,
    "aria-label": "Volume",
  }) as HTMLInputElement;
  vol.addEventListener("input", () => {
    adjustingVol = true;
    conn().setVolume(Number(vol.value));
  });
  vol.addEventListener("change", () => {
    adjustingVol = false;
  });

  // shuffle / repeat
  const btnShuffle = el(
    "button",
    { class: "modebtn", "aria-label": "Shuffle" },
    icon("🔀"),
  );
  const btnRepeat = el(
    "button",
    { class: "modebtn", "aria-label": "Repeat" },
    icon("🔁"),
  );

  const root = el("section", { class: "screen np" }, [
    art,
    el("div", { class: "np-meta" }, [title, artist]),
    el("div", { class: "np-scrub-row" }, [
      curTime,
      scrub,
      durTime,
    ]),
    el("div", { class: "np-transport" }, [btnPrev, btnPlay, btnNext]),
    el("div", { class: "np-mode-row" }, [
      btnShuffle,
      el("div", { class: "np-vol" }, [icon("🔈"), vol, icon("🔊")]),
      btnRepeat,
    ]),
  ]);

  const repeatNext: Record<RepeatMode, RepeatMode> = {
    off: "all",
    all: "one",
    one: "off",
  };

  btnShuffle.addEventListener("click", () => {
    const d = lastAudioShuffle;
    conn().setShuffle(!d);
  });
  btnRepeat.addEventListener("click", () => {
    conn().setRepeat(repeatNext[lastRepeat]);
  });
  btnPlay.addEventListener("click", () => {
    if (lastPlaying) conn().pause();
    else conn().play();
  });

  let lastPlaying = false;
  let lastRepeat: RepeatMode = "off";
  let lastAudioShuffle = false;

  return {
    el: root,
    update(state: AppState) {
      const a = state.device?.audio;
      if (!a) {
        title.textContent = "Not connected";
        artist.textContent = "—";
        return;
      }
      lastPlaying = a.playing;
      lastRepeat = a.repeat;
      lastAudioShuffle = a.shuffle;

      title.textContent = a.track?.title ?? "No track";
      artist.textContent = a.track?.artist ?? "—";
      art.classList.toggle("spinning", a.playing);

      btnPlay.replaceChildren(icon(a.playing ? "⏸" : "▶"));

      const dur = a.track?.durationS ?? 0;
      durTime.textContent = mmss(dur);
      scrub.max = String(Math.max(1, Math.floor(dur)));
      if (!seeking) {
        scrub.value = String(Math.floor(a.positionS));
        curTime.textContent = mmss(a.positionS);
      }
      const played = dur ? (a.positionS / dur) * 100 : 0;
      scrub.style.setProperty("--pct", `${played}%`);

      if (!adjustingVol) vol.value = String(a.volume);
      vol.style.setProperty("--pct", `${a.volume}%`);

      btnShuffle.classList.toggle("active", a.shuffle);
      btnRepeat.classList.toggle("active", a.repeat !== "off");
      btnRepeat.replaceChildren(icon(a.repeat === "one" ? "🔂" : "🔁"));
    },
  };
}
