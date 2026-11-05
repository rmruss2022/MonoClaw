// HighFi — AppState implementation.
#include "app_state.h"
#include "audio/audio_player.h"
#include "vape/coil_control.h"
#include "vape/safety.h"

AppState          g_state;
SemaphoreHandle_t g_stateMutex = nullptr;

// ------------------------------------------------------------------- init ----
void appStateInit() {
    g_stateMutex = xSemaphoreCreateMutex();

    // Safe defaults everywhere. In particular: LOCKED and NOT firing.
    memset(&g_state, 0, sizeof(g_state));

    g_state.audio.playing  = false;
    g_state.audio.volume   = AUDIO_VOLUME_DEFAULT;
    strncpy(g_state.audio.repeat, "off", sizeof(g_state.audio.repeat));
    g_state.audio.shuffle  = false;

    g_state.vape.locked      = true;                 // ships LOCKED (SAFETY.md §6)
    g_state.vape.firing      = false;
    g_state.vape.mode        = VapeMode::VOLTAGE;
    g_state.vape.setVolts    = VAPE_VOLTS_DEFAULT;
    g_state.vape.setWatts    = VAPE_WATTS_DEFAULT;
    g_state.vape.coilOhms    = 0.0f;
    g_state.vape.coilTempC   = 25.0f;
    g_state.vape.sessionS    = 0;
    g_state.vape.cartPresent = false;

    g_state.power.battPct = 0;
    g_state.power.charging = false;
    g_state.power.voltage  = 0.0f;

    strncpy(g_state.device.name, HIGHFI_DEVICE_NAME, sizeof(g_state.device.name));
    strncpy(g_state.device.fw,   HIGHFI_FW_VERSION,  sizeof(g_state.device.fw));
    strncpy(g_state.device.wifi, "disconnected",     sizeof(g_state.device.wifi));
    strncpy(g_state.device.ip,   "0.0.0.0",          sizeof(g_state.device.ip));
}

bool stateLock(TickType_t timeout) {
    if (!g_stateMutex) return false;
    return xSemaphoreTake(g_stateMutex, timeout) == pdTRUE;
}

void stateUnlock() {
    if (g_stateMutex) xSemaphoreGive(g_stateMutex);
}

// ------------------------------------------------------------- serialize -----
static const char* vapeModeStr(VapeMode m) {
    return m == VapeMode::WATTS ? "watts" : "voltage";
}

void appStateToJson(JsonDocument& doc) {
    doc["t"] = "state";

    // Copy under lock into locals, then build JSON without holding it.
    AppState s;
    if (stateLock(pdMS_TO_TICKS(50))) {
        s = g_state;
        stateUnlock();
    } else {
        s = g_state;   // best-effort; a stale snapshot is fine for a status push
    }

    JsonObject audio = doc["audio"].to<JsonObject>();
    audio["playing"] = s.audio.playing;
    JsonObject track = audio["track"].to<JsonObject>();
    track["id"]        = s.audio.track.id;
    track["title"]     = s.audio.track.title;
    track["artist"]    = s.audio.track.artist;
    track["durationS"] = s.audio.track.durationS;
    audio["positionS"] = s.audio.positionS;
    audio["volume"]    = s.audio.volume;
    audio["repeat"]    = s.audio.repeat;
    audio["shuffle"]   = s.audio.shuffle;

    JsonObject vape = doc["vape"].to<JsonObject>();
    vape["locked"]      = s.vape.locked;
    vape["firing"]      = s.vape.firing;
    vape["mode"]        = vapeModeStr(s.vape.mode);
    vape["setVolts"]    = serialized(String(s.vape.setVolts, 1));
    vape["setWatts"]    = serialized(String(s.vape.setWatts, 0));
    vape["coilOhms"]    = serialized(String(s.vape.coilOhms, 2));
    vape["coilTempC"]   = (int)lroundf(s.vape.coilTempC);
    vape["sessionS"]    = s.vape.sessionS;
    vape["cartPresent"] = s.vape.cartPresent;

    JsonObject power = doc["power"].to<JsonObject>();
    power["battPct"]  = s.power.battPct;
    power["charging"] = s.power.charging;
    power["voltage"]  = serialized(String(s.power.voltage, 2));

    JsonObject device = doc["device"].to<JsonObject>();
    device["name"] = s.device.name;
    device["fw"]   = s.device.fw;
    device["wifi"] = s.device.wifi;
    device["ip"]   = s.device.ip;
}

// ------------------------------------------------------------- commands ------
bool appStateApplyCommand(const Command& cmd) {
    switch (cmd.kind) {

        case CmdKind::AUDIO: {
            switch (cmd.audioVerb) {
                case AudioVerb::PLAY:  audioPlay();  break;
                case AudioVerb::PAUSE: audioPause(); break;
                case AudioVerb::NEXT:  audioNext();  break;
                case AudioVerb::PREV:  audioPrev();  break;
                case AudioVerb::STOP:  audioStop();  break;
                default: return false;
            }
            return true;
        }

        case CmdKind::SEEK:
            audioSeek((uint32_t)max(0, cmd.intArg));
            return true;

        case CmdKind::VOLUME: {
            uint8_t v = (uint8_t)constrain(cmd.intArg, 0, 100);
            audioSetVolume(v);
            if (stateLock()) { g_state.audio.volume = v; stateUnlock(); }
            return true;
        }

        case CmdKind::PLAY_TRACK:
            return audioPlayTrack(cmd.strArg);

        case CmdKind::VAPE_FIRE:
            // UNTRUSTED. We only record the *request*. controlTask + safety
            // decide whether the coil actually energizes, every tick.
            coilRequestFire(cmd.boolArg, FireSource::NET);
            return true;

        case CmdKind::VAPE_SET: {
            // Clamp to the safe window BEFORE storing. safety owns the clamp so
            // there is exactly one place that defines "safe".
            VapeMode mode  = cmd.mode;
            float    volts = cmd.volts;
            float    watts = cmd.watts;
            safetyClampSetpoint(mode, volts, watts);
            coilSetSetpoint(mode, volts, watts);
            if (stateLock()) {
                g_state.vape.mode     = mode;
                g_state.vape.setVolts = volts;
                g_state.vape.setWatts = watts;
                stateUnlock();
            }
            return true;
        }

        case CmdKind::VAPE_LOCK:
            // The app may LOCK at will (always safe). It may NOT remotely unlock
            // the fire path — physical 5-click is required to unlock (SAFETY §6).
            if (cmd.boolArg) {
                safetyLock();
            } else {
                // ignore remote-unlock; log for the app to explain in UI.
                log_w("remote unlock ignored; use physical 5-click");
                return false;
            }
            return true;

        case CmdKind::LED_PRESET:
            // Cosmetic only; handled by uiTask/display. Store nothing critical.
            displaySetLedPreset(cmd.strArg);
            return true;

        default:
            return false;
    }
}
