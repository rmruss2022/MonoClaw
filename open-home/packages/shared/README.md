# packages/shared

The contract every service agrees on: normalized device types and event schemas.

- `Device`, `DeviceEvent`, `Capability` types.
- Zod schemas so hub, device-gateway, and app validate identical shapes.

Keeping the core protocol-agnostic lives here — adapters translate vendor protocols
into these types and nothing else.

Status: stub (ROADMAP Phase 0/1).
