# services/storage

The NAS layer. Owns everything that must stay on the user's disk.

- **Recordings**: camera clips with retention policies + ring-buffer eviction.
- **Metadata DB**: SQLite for a single box, Postgres for larger installs.
- **Backup/export**: users can move their data off the box any time — no lock-in.

Privacy rule: raw video/audio never leaves this box unless the user explicitly enables a
cloud feature for a specific stream.

Status: stub (ROADMAP Phase 1).
