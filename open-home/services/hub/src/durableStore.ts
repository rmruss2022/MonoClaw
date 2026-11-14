/**
 * Durable JSON store — crash-safe persistence for small config files. fsync before
 * rename + a .bak mirror that recovers if the primary is ever NUL-corrupted by an
 * unclean reboot. (Self-contained; only used by sceneConfig here.)
 */
import { readFileSync, writeFileSync, mkdirSync, renameSync, openSync, fsyncSync, closeSync, copyFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

function fsyncPath(path: string) {
  try { const fd = openSync(path, "r"); try { fsyncSync(fd); } finally { closeSync(fd); } } catch { /* best effort */ }
}

function tryParse<T>(path: string): T | undefined {
  try {
    const raw = readFileSync(path, "utf8");
    if (!raw || raw.indexOf("\0") !== -1) return undefined;
    return JSON.parse(raw) as T;
  } catch { return undefined; }
}

export interface DurableStore<T> { load: (fallback: T) => T; save: (data: T) => void }

export function durableStore<T>(dataDirUrl: URL, fileName: string, label: string): DurableStore<T> {
  const dir = fileURLToPath(dataDirUrl);
  const main = fileURLToPath(new URL(fileName, dataDirUrl));
  const tmp = fileURLToPath(new URL(fileName + ".tmp", dataDirUrl));
  const bak = fileURLToPath(new URL(fileName + ".bak", dataDirUrl));

  function load(fallback: T): T {
    const primary = tryParse<T>(main);
    if (primary !== undefined) { try { copyFileSync(main, bak); } catch { /* ignore */ } return primary; }
    const backup = tryParse<T>(bak);
    if (backup !== undefined) {
      console.log(`[${label}] primary store corrupt — recovered from backup`);
      try { copyFileSync(bak, main); } catch { /* ignore */ }
      return backup;
    }
    return fallback;
  }

  function save(data: T): void {
    try {
      mkdirSync(dir, { recursive: true });
      writeFileSync(tmp, JSON.stringify(data));
      fsyncPath(tmp);
      renameSync(tmp, main);
      fsyncPath(dir);
      try { copyFileSync(main, bak); fsyncPath(bak); } catch { /* best effort */ }
    } catch (e) { console.log(`[${label}] save:`, (e as Error).message); }
  }

  return { load, save };
}
