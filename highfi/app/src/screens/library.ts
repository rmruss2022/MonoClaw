import type { Screen } from "../ui/screen.ts";
import type { AppState } from "../state.ts";
import { el, icon } from "../ui/dom.ts";
import { mmss } from "../ui/format.ts";
import { getConnection } from "../connectionManager.ts";
import type { Track } from "../protocol.ts";

export function createLibrary(): Screen {
  const conn = () => getConnection();

  const list = el("div", { class: "lib-list" });

  const uploadInput = el("input", {
    type: "file",
    accept: "audio/*",
    class: "hidden",
    multiple: true,
  }) as HTMLInputElement;

  const uploadNote = el("p", { class: "lib-upload-note" });

  uploadInput.addEventListener("change", () => {
    void handleUpload(uploadInput.files, uploadNote);
    uploadInput.value = "";
  });

  const uploadBtn = el(
    "button",
    { class: "btn ghost lib-upload", onclick: () => uploadInput.click() },
    [icon("⬆"), "Upload tracks"],
  );

  const header = el("div", { class: "lib-header" }, [
    el("h1", { class: "screen-title" }, "Library"),
    uploadBtn,
  ]);

  const root = el("section", { class: "screen lib" }, [
    header,
    uploadInput,
    uploadNote,
    list,
  ]);

  let renderedIds = "";
  let currentId: string | null = null;

  function renderList(tracks: Track[], playingId: string | null): void {
    list.replaceChildren();
    if (tracks.length === 0) {
      list.append(
        el("p", { class: "empty" }, "No tracks on device yet. Upload some."),
      );
      return;
    }
    for (const t of tracks) {
      const active = t.id === playingId;
      const row = el(
        "button",
        {
          class: `lib-row${active ? " active" : ""}`,
          onclick: () => conn().playTrack(t.id),
        },
        [
          el("span", { class: "lib-idx" }, active ? icon("♪") : t.id),
          el("span", { class: "lib-info" }, [
            el("span", { class: "lib-title" }, t.title),
            el("span", { class: "lib-artist" }, t.artist),
          ]),
          el("span", { class: "lib-dur" }, mmss(t.durationS)),
        ],
      );
      list.append(row);
    }
  }

  return {
    el: root,
    onEnter() {
      conn().requestLibrary();
    },
    update(state: AppState) {
      const ids = state.library.map((t) => t.id).join(",");
      const playingId = state.device?.audio.track?.id ?? null;
      if (ids !== renderedIds || playingId !== currentId) {
        renderedIds = ids;
        currentId = playingId;
        renderList(state.library, playingId);
      }
    },
  };
}

async function handleUpload(
  files: FileList | null,
  note: HTMLElement,
): Promise<void> {
  if (!files || files.length === 0) return;
  note.textContent = `Uploading ${files.length} file(s)…`;
  const form = new FormData();
  for (const f of Array.from(files)) form.append("track", f, f.name);
  try {
    // Stubbed endpoint — real firmware exposes POST /api/upload (SPEC §3.6).
    const res = await fetch("/api/upload", { method: "POST", body: form });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    note.textContent = "Upload complete.";
  } catch (err) {
    note.textContent = `Upload stub (no device): would POST /api/upload — ${String(
      err,
    )}`;
  }
}
