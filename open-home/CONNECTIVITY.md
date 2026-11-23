# Hub ↔ App connectivity

How a phone finds and reaches a hub — for the owner on their sofa, for the owner
on a train, and for the next thousand customers who will not read a manual.

## The problem

The cloud is a **directory, not a data plane**. After sign-in the app talks
straight to the hub, which means the app must learn *an address that works right
now*. That address changes with where the phone is:

| Phone is… | Reachable via |
|---|---|
| On home WiFi | `http://192.168.0.120:4700` — fastest, private, no cloud |
| On cellular | a tunnel hostname, or the owner's own DNS |
| On a VPN/tailnet | `http://100.x.y.z:4700` |

Today none of these are discovered: the hub never tells anyone where it is, and
the app has no way to find out. That is the whole bug.

## Design

### 1. The hub publishes its own addresses

The hub knows its addresses better than anything else does. On boot and every
5 minutes it POSTs a **presence record** to the cloud:

```jsonc
{
  "homeId":   "hm_...",
  "hubId":    "hub_...",          // stable, derived from machine-id
  "version":  "1.4.0",
  "addresses": [
    { "kind": "lan",    "url": "http://192.168.0.120:4700", "priority": 10 },
    { "kind": "tailnet","url": "http://100.124.114.121:4700","priority": 20 },
    { "kind": "tunnel", "url": "https://home-ab12cd.openhome.app", "priority": 30 },
    { "kind": "custom", "url": "https://home.bedrock.casa",  "priority": 5  }
  ]
}
```

Lower priority wins. **Custom beats everything** — if an owner has configured
their own DNS they have opinions, and we respect them. LAN beats tunnel because
it is faster, cheaper and never leaves the house.

### 2. The app resolves in order, and remembers what worked

```
loadSession()
  ├─ cached address that worked last time   → try first (fast path, offline-capable)
  ├─ addresses from cloud /api/home         → try in priority order
  ├─ mDNS on the local network              → works with no cloud at all
  └─ none reachable                         → onboarding: pair, or enter a URL
```

Each candidate gets a **1.5 s** `/health` probe, raced in parallel rather than
tried serially — on a bad network, serial fallback feels broken. First healthy
answer wins and is cached as `lastGood`.

### 3. Pairing, for people who have never used a terminal

The hub shows a **6-character code** (web UI, console, and spoken on request).
In the app: *Add a hub → enter code*. The cloud matches code → hub, links it to
the account, and returns its addresses.

Codes are single-use, expire in 10 minutes, and are rate-limited. A code only
ever grants *linking*; it is never an access token.

### 4. Managed tunnel — the default that just works

Most customers will never configure DNS. For them the hub requests a tunnel
hostname from the cloud at first boot and runs `cloudflared`. They get
`https://home-ab12cd.openhome.app` and never think about it again.

### 5. Custom DNS — the escape hatch

Set `OPEN_HOME_PUBLIC_URL=https://home.example.com` on the hub, or enter it in
the app under Settings → Advanced. It is published as a `custom` address at the
highest priority, and can be used **with the managed tunnel disabled entirely**
for owners who want nothing of theirs touching our infrastructure.

### 6. Caching is opt-in, and means something specific

`cacheDirectory` on the account:

- **on** (default): the cloud retains the hub's addresses, so a fresh install
  signs in and connects immediately with no LAN discovery and no code.
- **off**: the cloud stores only `homeId` + `hubId`. Addresses are held in
  memory for the lifetime of a request and never written. The app must then
  discover over mDNS, or the owner enters a URL. Slower, and entirely private.

This is a real switch, not a label: with it off there is no address in the
database to leak, subpoena or breach.

## Onboarding

```
Welcome ─► Sign in ─► Finding your hub…
                        ├─ found on this network     → Connected ✅
                        ├─ found via your account    → Connected ✅
                        └─ not found
                             ├─ Enter pairing code
                             ├─ Enter hub address manually
                             └─ Help me set up a hub
```

"Finding your hub" runs LAN discovery and the cloud lookup **concurrently** and
takes whichever answers first. The failure screen never dead-ends — every branch
offers a next step.

## Security notes

- The home token is a **grant for one home**, not an account credential, and is
  scoped so a stolen phone can be revoked without changing a password.
- The hub only accepts a registration POST signed with `HOME_TOKEN_SECRET`, so a
  third party cannot re-point someone's home at a hub they control.
- Addresses are not secrets, but they are *location-revealing*; that is why
  caching is opt-out-able.
