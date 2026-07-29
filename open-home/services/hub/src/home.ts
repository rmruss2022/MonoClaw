/**
 * A mock but realistic home model — rooms, ~30 devices across many types, scenes,
 * a tiny NLU, and an ambient-event simulator. This stands in for the device-gateway
 * (MQTT/Matter) until Phase 1, but the shape (normalized devices + a bus) is the real one.
 *
 * Everything here is pure state + logic. The hub owns the event bus and publishes;
 * this module just mutates and reports.
 */

export interface Device {
  id: string;
  name: string;
  type: string;   // light | lock | camera | doorbell | speaker | thermostat | sensor | plug | garage | shade | vacuum
  room: string;
  icon: string;
  state: Record<string, any>;
}

export interface Scene { id: string; name: string; icon: string; description: string; }

export const ROOMS = [
  "Entry", "Living Room", "Kitchen", "Bedroom", "Office", "Bathroom", "Hallway", "Garage", "Backyard",
];

function d(id: string, name: string, type: string, room: string, icon: string, state: Record<string, any>): Device {
  return { id, name, type, room, icon, state };
}

const devices: Device[] = [
  // Lights
  d("light_living", "Living Room Lights", "light", "Living Room", "💡", { on: false, brightness: 80 }),
  d("light_kitchen", "Kitchen Lights", "light", "Kitchen", "💡", { on: false, brightness: 90 }),
  d("light_bedroom", "Bedroom Lights", "light", "Bedroom", "💡", { on: false, brightness: 60 }),
  d("light_office", "Office Lights", "light", "Office", "💡", { on: false, brightness: 100 }),
  d("light_bathroom", "Bathroom Lights", "light", "Bathroom", "💡", { on: false, brightness: 70 }),
  d("light_hallway", "Hallway Lights", "light", "Hallway", "💡", { on: false, brightness: 50 }),
  d("light_porch", "Porch Light", "light", "Entry", "💡", { on: true, brightness: 100 }),
  // Locks
  d("lock_front", "Front Door", "lock", "Entry", "🔒", { locked: true }),
  d("lock_back", "Back Door", "lock", "Kitchen", "🔒", { locked: true }),
  d("lock_garage", "Garage Entry", "lock", "Garage", "🔒", { locked: true }),
  // Cameras
  d("cam_front", "Front Door Cam", "camera", "Entry", "📷", { online: true, recording: true, lastMotion: null }),
  d("cam_backyard", "Backyard Cam", "camera", "Backyard", "📷", { online: true, recording: true, lastMotion: null }),
  d("cam_garage", "Garage Cam", "camera", "Garage", "📷", { online: true, recording: true, lastMotion: null }),
  d("cam_living", "Living Room Cam", "camera", "Living Room", "📷", { online: true, recording: false, lastMotion: null }),
  // Doorbell
  d("doorbell_front", "Front Doorbell", "doorbell", "Entry", "🔔", { online: true, lastRing: null }),
  // Speakers / media
  d("speaker_living", "Living Room Speaker", "speaker", "Living Room", "🔊", { playing: false, volume: 30, track: "—" }),
  d("speaker_kitchen", "Kitchen Speaker", "speaker", "Kitchen", "🔊", { playing: false, volume: 25, track: "—" }),
  d("speaker_bedroom", "Bedroom Speaker", "speaker", "Bedroom", "🔊", { playing: false, volume: 20, track: "—" }),
  // Climate
  d("thermostat_main", "Thermostat", "thermostat", "Hallway", "🌡️", { temp: 71, target: 70, mode: "auto" }),
  // Sensors
  d("sensor_front_contact", "Front Door Sensor", "sensor", "Entry", "🚪", { kind: "contact", open: false }),
  d("sensor_bed_motion", "Bedroom Motion", "sensor", "Bedroom", "🚶", { kind: "motion", motion: false }),
  d("sensor_living_motion", "Living Room Motion", "sensor", "Living Room", "🚶", { kind: "motion", motion: false }),
  d("sensor_kitchen_th", "Kitchen Climate", "sensor", "Kitchen", "💧", { kind: "climate", temp: 70, humidity: 44 }),
  // Plugs
  d("plug_coffee", "Coffee Maker", "plug", "Kitchen", "🔌", { on: false }),
  d("plug_tv", "TV", "plug", "Living Room", "🔌", { on: false }),
  // Garage door
  d("garage_door", "Garage Door", "garage", "Garage", "🚗", { open: false }),
  // Shades
  d("shade_living", "Living Room Shades", "shade", "Living Room", "🪟", { position: 60 }),
  d("shade_bedroom", "Bedroom Shades", "shade", "Bedroom", "🪟", { position: 40 }),
  // Vacuum
  d("vacuum_robo", "Robot Vacuum", "vacuum", "Living Room", "🧹", { status: "docked", battery: 92 }),
];

const SCENES: Scene[] = [
  { id: "good_morning", name: "Good Morning", icon: "☀️", description: "Lights up, coffee on, unlock, shades open." },
  { id: "good_night", name: "Good Night", icon: "🌙", description: "Lights off, doors locked, shades down, cooler." },
  { id: "movie", name: "Movie", icon: "🎬", description: "Dim living room, TV on, shades closed." },
  { id: "away", name: "Away", icon: "🚪", description: "Everything off, locked, cameras recording." },
  { id: "home", name: "I'm Home", icon: "🏡", description: "Unlock, warm up, entry + living lights on." },
  { id: "dinner", name: "Dinner", icon: "🍽️", description: "Warm kitchen + living lights, soft music." },
  { id: "party", name: "Party", icon: "🎉", description: "Every light full, music up, shades open." },
  { id: "reading", name: "Reading", icon: "📖", description: "Soft office + living light, quiet everywhere else." },
];

let currentScene: string | null = null;

const byType = (t: string) => devices.filter((x) => x.type === t);
export function getDevice(id: string) { return devices.find((x) => x.id === id); }
export function allDevices() { return devices; }
export function getScenes() { return SCENES; }
function getScene(id: string) { return SCENES.find((s) => s.id === id); }

export function setDevice(id: string, patch: Record<string, any>) {
  const dev = getDevice(id);
  if (!dev) return null;
  Object.assign(dev.state, patch);
  return dev;
}

function set(id: string, patch: Record<string, any>) { setDevice(id, patch); }

export function setByType(type: string, patch: Record<string, any>) {
  byType(type).forEach((d) => Object.assign(d.state, patch));
}

export function activateScene(id: string): Scene | { id: string } {
  switch (id) {
    case "good_morning":
      set("light_living", { on: true, brightness: 80 }); set("light_kitchen", { on: true, brightness: 90 });
      set("light_bathroom", { on: true, brightness: 70 });
      set("lock_front", { locked: false });
      set("thermostat_main", { target: 70, mode: "auto" });
      set("plug_coffee", { on: true });
      byType("shade").forEach((s) => (s.state.position = 80));
      set("speaker_kitchen", { playing: true, track: "Morning Mix" });
      break;
    case "good_night":
      byType("light").forEach((l) => (l.state.on = false));
      set("light_porch", { on: true });
      byType("lock").forEach((l) => (l.state.locked = true));
      byType("speaker").forEach((s) => (s.state.playing = false));
      set("thermostat_main", { target: 66 });
      byType("shade").forEach((s) => (s.state.position = 0));
      set("plug_coffee", { on: false }); set("garage_door", { open: false });
      break;
    case "movie":
      set("light_living", { on: true, brightness: 15 });
      set("light_kitchen", { on: false }); set("light_hallway", { on: false });
      set("plug_tv", { on: true });
      set("speaker_living", { playing: true, track: "Movie Ambience", volume: 45 });
      set("shade_living", { position: 0 });
      break;
    case "away":
      byType("light").forEach((l) => (l.state.on = false));
      set("light_porch", { on: true });
      byType("lock").forEach((l) => (l.state.locked = true));
      byType("camera").forEach((c) => { c.state.recording = true; });
      byType("plug").forEach((p) => (p.state.on = false));
      byType("speaker").forEach((s) => (s.state.playing = false));
      set("thermostat_main", { target: 62, mode: "auto" });
      set("garage_door", { open: false });
      break;
    case "home":
      set("light_porch", { on: true }); set("light_living", { on: true, brightness: 70 });
      set("light_hallway", { on: true, brightness: 50 });
      set("lock_front", { locked: false });
      set("thermostat_main", { target: 70 });
      break;
    case "dinner":
      set("light_kitchen", { on: true, brightness: 70 }); set("light_living", { on: true, brightness: 50 });
      set("speaker_kitchen", { playing: true, track: "Dinner Jazz", volume: 25 });
      break;
    case "party":
      byType("light").forEach((l) => { l.state.on = true; l.state.brightness = 100; });
      byType("speaker").forEach((s) => { s.state.playing = true; s.state.track = "Party Mix"; s.state.volume = 60; });
      set("plug_tv", { on: false }); byType("shade").forEach((s) => (s.state.position = 100));
      break;
    case "reading":
      byType("light").forEach((l) => (l.state.on = false));
      set("light_living", { on: true, brightness: 40 }); set("light_office", { on: true, brightness: 70 });
      byType("speaker").forEach((s) => (s.state.playing = false));
      set("plug_tv", { on: false });
      break;
  }
  currentScene = id;
  return getScene(id) ?? { id };
}

// Map the radial control's 8 actions to real devices/scenes.
export function control(action: string): { on?: boolean; label?: string; scene?: string } {
  switch (action) {
    case "lights": {
      const lights = byType("light").filter((l) => l.id !== "light_porch");
      const anyOn = lights.some((l) => l.state.on);
      lights.forEach((l) => (l.state.on = !anyOn));
      return { on: !anyOn, label: !anyOn ? "on" : "off" };
    }
    case "lock": {
      const locks = byType("lock");
      const anyUnlocked = locks.some((l) => !l.state.locked);
      locks.forEach((l) => (l.state.locked = anyUnlocked));
      return { on: anyUnlocked, label: anyUnlocked ? "locked" : "unlocked" };
    }
    case "music": {
      const s = getDevice("speaker_living")!;
      s.state.playing = !s.state.playing;
      if (s.state.playing && s.state.track === "—") s.state.track = "Chill Mix";
      return { on: s.state.playing, label: s.state.playing ? "playing" : "paused" };
    }
    case "cameras": return { label: "viewing" };
    case "doorbell": return { label: "front door" };
    case "matthews_room": {
      set("light_bedroom", { on: true, brightness: 75 });
      set("speaker_bedroom", { playing: true, track: "Matthew's Mix" });
      set("shade_bedroom", { position: 60 });
      return { on: true, label: "Matthew's room on" };
    }
    case "party": activateScene("party"); return { scene: "party", label: "party" };
    case "reading": activateScene("reading"); return { scene: "reading", label: "reading" };
    case "away": activateScene("away"); return { scene: "away", label: "away" };
    case "movie": activateScene("movie"); return { scene: "movie", label: "scene set" };
    case "goodnight": case "nighttime": activateScene("good_night"); return { scene: "good_night", label: "night scene" };
    case "morning": activateScene("good_morning"); return { scene: "good_morning", label: "morning scene" };
    default: return {};
  }
}

// Tiny on-device NLU (stand-in for the local LLM agent).
export function respond(textRaw: string): { understood: boolean; action?: string; reply: string } {
  const t = (textRaw || "").toLowerCase();
  const has = (...w: string[]) => w.some((x) => t.includes(x));
  const off = has("off", "stop", "pause", "disable");
  const ROOM_LIGHTS: [string, string][] = [
    ["living", "light_living"], ["kitchen", "light_kitchen"], ["bedroom", "light_bedroom"],
    ["office", "light_office"], ["bathroom", "light_bathroom"], ["hall", "light_hallway"], ["porch", "light_porch"],
  ];
  let action: string | undefined, reply: string;

  if (has("good night", "goodnight", "night", "bed", "sleep")) { activateScene("good_night"); action = "good_night"; reply = "Good night 🌙 — lights off, doors locked, set for sleep."; }
  else if (has("good morning", "morning", "wake")) { activateScene("good_morning"); action = "good_morning"; reply = "Good morning ☀️ — lights up, coffee on, front door unlocked."; }
  else if (has("movie", "cinema", "film")) { activateScene("movie"); action = "movie"; reply = "Movie time 🎬 — dimming the living room and rolling the TV."; }
  else if (has("away", "leaving", "goodbye")) { activateScene("away"); action = "away"; reply = "Away mode 🚪 — locked up, lights off, cameras recording."; }
  else if (has("i'm home", "im home", "i am home", "welcome")) { activateScene("home"); action = "home"; reply = "Welcome home 🏡 — unlocked and lit up."; }
  else if (has("dinner")) { activateScene("dinner"); action = "dinner"; reply = "Dinner scene 🍽️ — warm lights and some jazz."; }
  else if (has("temperature", "thermostat", "degree", "warmer", "cooler", "heat", "cool")) {
    const m = t.match(/(\d{2})/); const dev = getDevice("thermostat_main")!;
    if (m) dev.state.target = Number(m[1]);
    else if (has("warmer", "heat")) dev.state.target += 2;
    else if (has("cooler", "cool")) dev.state.target -= 2;
    action = "thermostat"; reply = `Set the thermostat to ${dev.state.target}° 🌡️.`;
  }
  else if (has("light", "lamp")) {
    const room = ROOM_LIGHTS.find((r) => t.includes(r[0]));
    if (room) { const dev = getDevice(room[1])!; dev.state.on = !off; action = "lights"; reply = `${dev.name} ${dev.state.on ? "on 💡" : "off"}.`; }
    else { byType("light").filter((l) => l.id !== "light_porch").forEach((l) => (l.state.on = !off)); action = "lights"; reply = `All lights ${off ? "off" : "on 💡"}.`; }
  }
  else if (has("unlock")) { byType("lock").forEach((l) => (l.state.locked = false)); action = "lock"; reply = "Doors unlocked 🔓."; }
  else if (has("lock")) { byType("lock").forEach((l) => (l.state.locked = true)); action = "lock"; reply = "All doors locked 🔒."; }
  else if (has("garage")) { const g = getDevice("garage_door")!; g.state.open = has("open") ? true : has("close") ? false : !g.state.open; action = "garage"; reply = `Garage ${g.state.open ? "opening" : "closing"} 🚗.`; }
  else if (has("music", "song", "play", "spotify", "jazz")) { const s = getDevice("speaker_living")!; s.state.playing = !off; if (s.state.playing && s.state.track === "—") s.state.track = "Chill Mix"; action = "music"; reply = `Music ${s.state.playing ? "playing 🎵" : "paused"}.`; }
  else if (has("camera")) { action = "cameras"; reply = "Here are your cameras 📷 — all recording."; }
  else if (has("doorbell", "front door", "who's at", "whos at")) { action = "doorbell"; reply = "Showing the front door 🔔."; }
  else if (has("vacuum", "clean", "roomba")) { const v = getDevice("vacuum_robo")!; v.state.status = off ? "returning" : "cleaning"; action = "vacuum"; reply = `Vacuum ${v.state.status} 🧹.`; }
  else { reply = "Sorry, I didn't catch that. Try \"good night\", \"turn on the kitchen lights\", \"set it to 70\", or \"lock the doors\"."; }

  return { understood: !!action, action, reply };
}

// ---- display helpers ----
function isOn(dev: Device): boolean {
  switch (dev.type) {
    case "light": return !!dev.state.on;
    case "lock": return !!dev.state.locked;
    case "camera": return !!dev.state.recording;
    case "doorbell": return !!dev.state.online;
    case "speaker": return !!dev.state.playing;
    case "thermostat": return dev.state.mode !== "off";
    case "plug": return !!dev.state.on;
    case "garage": return !!dev.state.open;
    case "shade": return dev.state.position > 0;
    case "vacuum": return dev.state.status !== "docked";
    case "sensor": return !!(dev.state.motion || dev.state.open);
    default: return false;
  }
}
function label(dev: Device): string {
  switch (dev.type) {
    case "light": return dev.state.on ? `on · ${dev.state.brightness}%` : "off";
    case "lock": return dev.state.locked ? "locked" : "unlocked";
    case "camera": return dev.state.recording ? "recording" : "idle";
    case "doorbell": return dev.state.online ? "online" : "offline";
    case "speaker": return dev.state.playing ? `♪ ${dev.state.track}` : "paused";
    case "thermostat": return `${dev.state.temp}° → ${dev.state.target}° ${dev.state.mode}`;
    case "plug": return dev.state.on ? "on" : "off";
    case "garage": return dev.state.open ? "open" : "closed";
    case "shade": return `${dev.state.position}% open`;
    case "vacuum": return `${dev.state.status} · ${dev.state.battery}%`;
    case "sensor":
      if (dev.state.kind === "contact") return dev.state.open ? "open" : "closed";
      if (dev.state.kind === "motion") return dev.state.motion ? "motion" : "clear";
      return `${dev.state.temp}° · ${dev.state.humidity}%`;
    default: return "";
  }
}

export function flat() {
  return devices.map((dev) => ({
    id: dev.id, name: dev.name, type: dev.type, room: dev.room, icon: dev.icon,
    on: isOn(dev), state: label(dev), raw: dev.state,
  }));
}

export function summary() {
  const lights = byType("light");
  const lightsOn = lights.filter((l) => l.state.on).length;
  const locks = byType("lock");
  const thermo = getDevice("thermostat_main")!;
  return {
    devices: devices.length,
    rooms: ROOMS.length,
    lightsOn, lightsTotal: lights.length,
    allLocked: locks.every((l) => l.state.locked),
    anyPlaying: byType("speaker").some((s) => s.state.playing),
    temp: thermo.state.temp, target: thermo.state.target,
    scene: currentScene,
  };
}

export function snapshot() {
  return { rooms: ROOMS, devices: flat(), scenes: SCENES, summary: summary() };
}

// Ambient simulator: nudge the house so the event feed feels alive. Returns an event
// (or null) for the hub to publish; the hub calls this on a timer.
export function simulateTick(now: number): { type: string; payload: any } | null {
  const roll = Math.floor((now / 1000)) % 6; // deterministic-ish rotation (no Math.random needed)
  switch (roll) {
    case 0: { const c = getDevice("cam_front")!; c.state.lastMotion = now; return { type: "camera.motion", payload: { id: c.id, room: c.room } }; }
    case 1: { const s = getDevice("sensor_living_motion")!; s.state.motion = !s.state.motion; return { type: "sensor.motion", payload: { id: s.id, motion: s.state.motion } }; }
    case 2: { const th = getDevice("thermostat_main")!; th.state.temp += th.state.temp < th.state.target ? 1 : -1; return { type: "thermostat.drift", payload: { temp: th.state.temp } }; }
    case 3: { const c = getDevice("cam_backyard")!; c.state.lastMotion = now; return { type: "camera.motion", payload: { id: c.id, room: c.room } }; }
    case 4: { const k = getDevice("sensor_kitchen_th")!; k.state.humidity += k.state.humidity < 50 ? 1 : -1; return { type: "sensor.climate", payload: { humidity: k.state.humidity } }; }
    default: return null;
  }
}
