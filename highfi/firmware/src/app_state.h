// HighFi — AppState: the single, mutex-guarded device state.
// -----------------------------------------------------------------------------
// One struct, mirrored to the app over /ws exactly as SPEC.md §4 describes.
// Same "single state, push deltas" shape as the openhome hub. Every field here
// maps 1:1 to a JSON key in the protocol; changing one means changing both
// (firmware + app) in lockstep.
//
// Concurrency: all tasks read/write through stateLock()/stateUnlock(). Hold the
// lock only long enough to copy in/out — never while doing I/O or firing.
// -----------------------------------------------------------------------------
#pragma once

#include <Arduino.h>
#include <ArduinoJson.h>
#include "config.h"

// ------------------------------- sub-structs --------------------------------

enum class VapeMode : uint8_t { VOLTAGE, WATTS };

struct TrackInfo {
    char    id[8];        // library id, e.g. "07"
    char    title[64];
    char    artist[64];
    uint32_t durationS;
};

struct AudioState {
    bool      playing;
    TrackInfo track;
    uint32_t  positionS;
    uint8_t   volume;     // 0..100
    char      repeat[8];  // "off" | "one" | "all"
    bool      shuffle;
};

struct VapeState {
    bool     locked;      // ships true; 5-click to unlock
    bool     firing;      // true only while controlTask is actually driving PWM
    VapeMode mode;
    float    setVolts;    // clamped 2.5..3.6
    float    setWatts;    // clamped 5..15
    float    coilOhms;    // measured
    float    coilTempC;   // measured
    uint32_t sessionS;    // seconds of the current/last fire event
    bool     cartPresent; // derived from resistance being in the valid band
};

struct PowerState {
    uint8_t battPct;
    bool    charging;
    float   voltage;
};

struct DeviceState {
    char name[32];
    char fw[16];
    char wifi[16];        // "connected" | "ap" | "disconnected"
    char ip[20];
};

struct AppState {
    AudioState  audio;
    VapeState   vape;
    PowerState  power;
    DeviceState device;
};

// Global instance + its mutex. Prefer the lock helpers below over touching
// g_stateMutex directly.
extern AppState             g_state;
extern SemaphoreHandle_t    g_stateMutex;

void appStateInit();
bool stateLock(TickType_t timeout = portMAX_DELAY);
void stateUnlock();

// Serialize the full snapshot as {"t":"state", ...} per SPEC §4. Caller supplies
// a JsonDocument; this takes the lock internally.
void appStateToJson(JsonDocument& doc);

// ------------------------------ command model -------------------------------
// ws_server parses raw /ws JSON into one of these and hands it here. This layer
// (with vape/safety) does the validating + clamping; nothing downstream trusts
// the wire values.
enum class CmdKind : uint8_t {
    NONE,
    AUDIO,        // play|pause|next|prev|stop  -> field audioVerb
    SEEK,         // seekS
    VOLUME,       // volume 0..100
    PLAY_TRACK,   // playTrack id
    VAPE_FIRE,    // vape:"fire", on:bool  -> request only; controlTask gates it
    VAPE_SET,     // vapeSet {mode,volts|watts} -> clamped
    VAPE_LOCK,    // vapeLock bool
    LED_PRESET,   // led {preset}
};

enum class AudioVerb : uint8_t { NONE, PLAY, PAUSE, NEXT, PREV, STOP };

struct Command {
    CmdKind   kind      = CmdKind::NONE;
    AudioVerb audioVerb = AudioVerb::NONE;
    int32_t   intArg    = 0;        // seekS / volume
    bool      boolArg   = false;    // fire on / lock
    VapeMode  mode      = VapeMode::VOLTAGE;
    float     volts     = VAPE_VOLTS_DEFAULT;
    float     watts     = VAPE_WATTS_DEFAULT;
    char      strArg[32] = {0};     // track id / led preset
    bool      hasMode   = false;    // vapeSet specified a mode
};

// Apply a parsed command. Routes to audio_player / coil_control / safety and
// updates g_state. Returns false if the command was malformed enough to ignore.
// NOTE: fire is only *requested* here; the coil is driven solely by controlTask.
bool appStateApplyCommand(const Command& cmd);
