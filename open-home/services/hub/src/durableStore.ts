/**
 * Durable JSON store — crash- and power-loss-safe persistence for the hub's
 * small onboarding files (lights, climate, speakers).
 *
 * Why this exists: an atomic `rename()` guards against *concurrent writers*, but
 * it is NOT durable across a power cut. On ext4 (the Pi's SD card) the file's
 * size metadata can be committed while its data blocks are still dirty — a hard
 * reboot then brings the file back the right length but filled with NUL bytes.
 * That silently wiped every onboarded light (JSON.parse of NULs throws → []).
 *
 * Two defenses:
 *   1. fsync the temp file (and its directory) BEFORE/AFTER the rename, so the
 *      bytes are on stable storage, not just in the page cache.
 *   2. Keep a `.bak` mirror of the last good write. If the primary is ever found
 *      corrupt (NUL-filled / unparseable), load() transparently recovers from
 *      the backup and repairs the primary.
 */
import { readFileSync, writeFileSync, mkdirSync, renameSync, openSync, fsyncSync, closeSync, copyFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

function fsyncPath(path: string) {
  try { const fd = openSync(path, "r"); try { fsyncSync(fd); } finally { closeSync(fd); } } catch { /* best effort */ }
}

/** Parse JSON; return undefined (not throw) if the bytes are missing/corrupt/NUL-filled. */
function tryParse<T>(path: string): T | undefined {
  try {
    const raw = readFileSync(path, "utf8");
    if (!raw || raw.indexOf("\0") !== -1) return undefined; // NUL-filled = crash-corrupted
    return JSON.parse(raw) as T;
  } catch { return undefined; }
}

export interface DurableStore<T> {
  load: (fallback: T) => T;
  save: (data: T) => void;
}

/** Create a durable store bound to a data dir URL and a file name (e.g. "local-lights.json"). */
export function durableStore<T>(dataDirUrl: URL, fileName: string, label: string): DurableStore<T> {
  const dir = fileURLToPath(dataDirUrl);
  const main = fileURLToPath(new URL(fileName, dataDirUrl));
  const tmp = fileURLToPath(new URL(fileName + ".tmp", dataDirUrl));
  const bak = fileURLToPath(new URL(fileName + ".bak", dataDirUrl));

  function load(fallback: T): T {
    const primary = tryParse<T>(main);
    if (primary !== undefined) {
      // Primary is good; make sure the backup reflects it (cheap, best-effort).
      try { copyFileSync(main, bak); } catch { /* ignore */ }
      return primary;
    }
    // Primary missing or corrupt — try to recover from the backup.
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
      fsyncPath(tmp);                 // flush data blocks before we publish them
      renameSync(tmp, main);          // atomic swap
      fsyncPath(dir);                 // persist the rename in the directory entry
      try { copyFileSync(main, bak); fsyncPath(bak); } catch { /* backup is best-effort */ }
    } catch (e) {
      console.log(`[${label}] save:`, (e as Error).message);
    }
  }

  return { load, save };
}
