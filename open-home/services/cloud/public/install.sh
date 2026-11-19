#!/usr/bin/env bash
#
#   openhome — one-step installer
#   Usage:   curl -fsSL https://openhome.studio/install | bash
#
#   What it does (and nothing it doesn't — read it, it's yours):
#     1. Makes sure git, Node >=22 and Python 3 are present (installs if it can).
#     2. Clones the openhome repo to ~/openhome  (set OPENHOME_DIR to override).
#     3. Installs dependencies.
#     4. Writes a keys file at ~/.openhome/openhome.env for you to fill in.
#     5. Installs a background service so the hub starts on boot and relaunches
#        if it ever crashes — then starts it, listening for "Hey Jarvis".
#
#   Re-running is safe: it updates the code + deps and leaves your keys alone.
#   No telemetry. No account. Everything stays on your box.
#
set -euo pipefail

# ---------- config (override via env) ----------------------------------------
OPENHOME_DIR="${OPENHOME_DIR:-$HOME/openhome}"
OPENHOME_REPO="${OPENHOME_REPO:-https://github.com/rmruss2022/openhome.git}"
OPENHOME_BRANCH="${OPENHOME_BRANCH:-main}"
CONFIG_DIR="${OPENHOME_CONFIG_DIR:-$HOME/.openhome}"
ENV_FILE="$CONFIG_DIR/openhome.env"
NODE_MIN_MAJOR=22

# ---------- pretty output ----------------------------------------------------
if [ -t 1 ]; then B="$(printf '\033[1m')"; D="$(printf '\033[2m')"; G="$(printf '\033[32m')"; Y="$(printf '\033[33m')"; R="$(printf '\033[31m')"; X="$(printf '\033[0m')"; else B=""; D=""; G=""; Y=""; R=""; X=""; fi
say()  { printf '%s\n' "${B}▸ $*${X}"; }
ok()   { printf '%s\n' "  ${G}✓${X} $*"; }
warn() { printf '%s\n' "  ${Y}!${X} $*"; }
die()  { printf '%s\n' "${R}✗ $*${X}" >&2; exit 1; }

printf '\n%s\n%s\n\n' "${B}  openhome · one-step install${X}" "${D}  your home. your data. your keys.${X}"

# ---------- helpers ----------------------------------------------------------
have() { command -v "$1" >/dev/null 2>&1; }

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  if have sudo; then SUDO="sudo"; fi
fi

OS="$(uname -s)"
PM=""
if have apt-get; then PM="apt"; elif have dnf; then PM="dnf"; elif have pacman; then PM="pacman"; elif have brew; then PM="brew"; fi

pm_install() {
  # pm_install <debian/rpm pkg...> — best effort, non-fatal
  [ "$#" -gt 0 ] || return 0
  case "$PM" in
    apt)    $SUDO apt-get update -qq && $SUDO apt-get install -y -q "$@" ;;
    dnf)    $SUDO dnf install -y -q "$@" ;;
    pacman) $SUDO pacman -Sy --noconfirm "$@" ;;
    brew)   brew install "$@" ;;
    *)      return 1 ;;
  esac
}

node_major() { node -v 2>/dev/null | sed 's/^v\([0-9]*\).*/\1/'; }

# ---------- 1. prerequisites -------------------------------------------------
say "Checking prerequisites"

have git || { warn "git missing — installing"; pm_install git || die "Could not install git. Install it and re-run."; }
ok "git $(git --version 2>/dev/null | awk '{print $3}')"

# Node >= 22 (the hub runs TypeScript directly via Node's type-stripping loader)
need_node=1
if have node && [ -n "$(node_major)" ] && [ "$(node_major)" -ge "$NODE_MIN_MAJOR" ]; then need_node=0; fi
if [ "$need_node" -eq 1 ]; then
  warn "Node >=$NODE_MIN_MAJOR not found — installing"
  case "$PM" in
    apt)    curl -fsSL https://deb.nodesource.com/setup_22.x | $SUDO -E bash - >/dev/null 2>&1 && $SUDO apt-get install -y -q nodejs ;;
    dnf)    curl -fsSL https://rpm.nodesource.com/setup_22.x | $SUDO bash - >/dev/null 2>&1 && $SUDO dnf install -y -q nodejs ;;
    pacman) pm_install nodejs npm ;;
    brew)   brew install node@22 && brew link --overwrite --force node@22 2>/dev/null || true ;;
    *)      die "No supported package manager. Install Node >=$NODE_MIN_MAJOR from https://nodejs.org and re-run." ;;
  esac
fi
have node || die "Node install failed. Install Node >=$NODE_MIN_MAJOR and re-run."
[ -n "$(node_major)" ] && [ "$(node_major)" -ge "$NODE_MIN_MAJOR" ] || die "Node $(node -v) is too old (need >=$NODE_MIN_MAJOR)."
ok "node $(node -v)   npm $(npm -v 2>/dev/null || echo '?')"

have python3 || { warn "python3 missing — installing"; pm_install python3 python3-venv python3-pip || warn "Could not install python3 (voice assistant will be unavailable)"; }
have python3 && ok "python3 $(python3 -V 2>/dev/null | awk '{print $2}')"

# ---------- 2. clone / update ------------------------------------------------
say "Fetching openhome → $OPENHOME_DIR"
if [ -d "$OPENHOME_DIR/.git" ]; then
  git -C "$OPENHOME_DIR" fetch --quiet origin "$OPENHOME_BRANCH" || warn "fetch failed (offline?) — using local copy"
  git -C "$OPENHOME_DIR" checkout --quiet "$OPENHOME_BRANCH" 2>/dev/null || true
  git -C "$OPENHOME_DIR" pull --quiet --ff-only 2>/dev/null || warn "could not fast-forward — leaving local commits in place"
  ok "updated existing checkout"
else
  mkdir -p "$(dirname "$OPENHOME_DIR")"
  git clone --quiet --branch "$OPENHOME_BRANCH" --depth 1 "$OPENHOME_REPO" "$OPENHOME_DIR" \
    || die "git clone failed from $OPENHOME_REPO"
  ok "cloned"
fi

# ---------- 3. dependencies --------------------------------------------------
say "Installing dependencies"
( cd "$OPENHOME_DIR" && npm install --no-audit --no-fund --loglevel=error ) || die "npm install failed"
ok "hub dependencies ready"

# ---------- 4. keys file -----------------------------------------------------
say "Setting up your keys file"
mkdir -p "$CONFIG_DIR"
if [ ! -f "$ENV_FILE" ]; then
  cat > "$ENV_FILE" <<'ENV'
# openhome — your keys. This file stays on your machine. chmod 600.
# Fill in what you want; leave the rest blank. Restart the hub after editing:
#    systemctl --user restart openhome-hub     (or: openhome restart)

# ── The brain (required) ──────────────────────────────────────────────
# Claude runs the home. Get a key at https://console.anthropic.com
ANTHROPIC_API_KEY=

# ── Voice reply (optional) ────────────────────────────────────────────
# Lifelike speech so Jarvis talks back. https://elevenlabs.io
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM

# ── Music (optional) ──────────────────────────────────────────────────
# Spotify app credentials. https://developer.spotify.com/dashboard
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
SPOTIFY_REDIRECT_URI=http://localhost:4700/callback

# ── Calendar / extras (optional) ──────────────────────────────────────
GOOGLE_GENAI_TOKEN=
GEMINI_API_KEY=

# ── Local security ────────────────────────────────────────────────────
# Password to reach the hub from the app. Change this.
OPEN_HOME_PASSWORD=changeme
OPEN_HOME_PORT=4700
ENV
  chmod 600 "$ENV_FILE"
  ok "wrote $ENV_FILE  (fill in your keys)"
else
  ok "keeping existing $ENV_FILE"
fi

# ---------- 5. service / autostart ------------------------------------------
say "Installing the hub service"
NODE_BIN="$(command -v node)"
START_CMD="$NODE_BIN --experimental-strip-types $OPENHOME_DIR/services/hub/src/index.ts"

installed_service=0
if have systemctl && systemctl --user show-environment >/dev/null 2>&1; then
  UNIT_DIR="$HOME/.config/systemd/user"
  mkdir -p "$UNIT_DIR"
  cat > "$UNIT_DIR/openhome-hub.service" <<UNIT
[Unit]
Description=openhome hub — your home, your keys
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$OPENHOME_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$START_CMD
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
UNIT
  systemctl --user daemon-reload
  systemctl --user enable --now openhome-hub.service >/dev/null 2>&1 || true
  # keep the user service alive after logout (best-effort; harmless if it fails)
  have loginctl && $SUDO loginctl enable-linger "$(id -un)" >/dev/null 2>&1 || true
  installed_service=1
  ok "systemd user service openhome-hub installed + started"
fi

# Fallback launcher always written, so there's a simple way to run it by hand.
LAUNCH="$CONFIG_DIR/run-hub.sh"
cat > "$LAUNCH" <<RUN
#!/usr/bin/env bash
set -a; [ -f "$ENV_FILE" ] && . "$ENV_FILE"; set +a
cd "$OPENHOME_DIR"
exec $START_CMD
RUN
chmod +x "$LAUNCH"

# A tiny 'openhome' command (start/stop/restart/logs/edit) on the PATH if we can.
BIN_DIR="$HOME/.local/bin"; mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/openhome" <<CLI
#!/usr/bin/env bash
set -euo pipefail
case "\${1:-}" in
  start)   systemctl --user start openhome-hub 2>/dev/null || "$LAUNCH" ;;
  stop)    systemctl --user stop openhome-hub 2>/dev/null || pkill -f 'services/hub/src/index.ts' || true ;;
  restart) systemctl --user restart openhome-hub 2>/dev/null || { pkill -f 'services/hub/src/index.ts' || true; "$LAUNCH" & } ;;
  logs)    journalctl --user -u openhome-hub -f 2>/dev/null || echo "run: $LAUNCH" ;;
  edit)    "\${EDITOR:-nano}" "$ENV_FILE" ;;
  run)     "$LAUNCH" ;;
  *) echo "openhome: start | stop | restart | logs | edit | run"; echo "config: $ENV_FILE" ;;
esac
CLI
chmod +x "$BIN_DIR/openhome"
ok "command 'openhome' installed in $BIN_DIR"
case ":$PATH:" in *":$BIN_DIR:"*) : ;; *) warn "add to PATH:  export PATH=\"\$HOME/.local/bin:\$PATH\"";; esac

# ---------- done -------------------------------------------------------------
printf '\n%s\n' "${G}${B}✓ openhome is installed.${X}"
cat <<NEXT

  ${B}Next steps${X}
    1. Add your keys:      ${B}openhome edit${X}   ${D}(or edit $ENV_FILE)${X}
       → at minimum set ${B}ANTHROPIC_API_KEY${X} (the brain).
    2. Start / restart:    ${B}openhome restart${X}
    3. Open the dashboard: ${B}http://localhost:4700${X}
    4. Download the app and say ${B}"Hey Jarvis."${X}

  ${D}Voice wake-word ("Hey Jarvis") needs a mic — set it up with:${X}
    ${D}cd $OPENHOME_DIR/services/voice-client && cat README.md${X}

  Your home AI awaits. ✨

NEXT

if [ "$installed_service" -eq 0 ]; then
  warn "No systemd user session detected — start the hub manually with:  openhome run"
fi
