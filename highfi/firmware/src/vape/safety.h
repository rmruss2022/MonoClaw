// HighFi — safety: the interlock authority. FINAL SAY over the coil.
// -----------------------------------------------------------------------------
// Implements every hard interlock in hardware/SAFETY.md / SPEC §5:
//   1. 10 s hard fire cutoff
//   2. no-atomizer lockout (open / >3 ohm) and short cutoff (<0.15 ohm, latched)
//   3. over-temp cutoff (coil or cell NTC) with cool-down re-arm
//   4. over-current (soft; hardware INA IRQ is the real fast-path)
//   5. 5-click lock — device boots LOCKED; auto re-lock after inactivity
//   6. clamp every app setpoint to the safe window
//   7. fail-safe OFF on fault / reset / comms loss / watchdog
//
// controlTask calls safetyEvaluate() every tick and obeys the verdict. No other
// module may energize the coil.
// -----------------------------------------------------------------------------
#pragma once

#include <Arduino.h>
#include "app_state.h"   // VapeMode

enum class FaultCode : uint8_t {
    NONE,
    LOCKED,        // device is locked (not a "fault", but blocks fire)
    NO_ATOMIZER,   // open / > COIL_OHMS_OPEN
    SHORT,         // < COIL_OHMS_SHORT  (latched)
    OVER_TEMP,     // coil or cell NTC over threshold
    OVER_CURRENT,  // > COIL_CURRENT_MAX_A
    TIMEOUT,       // hit the 10 s cutoff
    COOLDOWN,      // enforced rest after a full-length fire or over-temp
    COMMS_LOSS,    // app/UI comms lost while a NET fire was requested
    WATCHDOG,      // watchdog / fault forced OFF
};

const char* faultCodeStr(FaultCode f);

// Everything safetyEvaluate needs for one decision. Assembled by controlTask.
struct SafetyInputs {
    bool     fireRequested;   // combined button|net request
    float    coilOhms;
    float    coilTempC;
    float    cellTempC;
    float    coilCurrentA;
    bool     cartPresent;
    uint32_t fireElapsedMs;   // continuous energized time this event
    bool     commsOk;         // false => treat NET-driven fire as unsafe
};

struct SafetyVerdict {
    bool      allowFire;
    FaultCode fault;
};

void safetyInit();

// The verdict. Pure w.r.t. inputs except it maintains internal latch/cool-down
// state (short latch, over-temp cool-down, timeout rest window).
SafetyVerdict safetyEvaluate(const SafetyInputs& in);

// Lock state (5-click). Device ships locked; only a physical gesture unlocks.
bool safetyIsLocked();
void safetyLock();
void safetyUnlock();
void safetyNoteActivity();          // resets the auto-relock timer
void safetyServiceAutoLock();       // called from controlTask; re-locks when idle

// Fault latch (short-circuit, etc). A latched fault blocks fire until cleared by
// removing the cart / user re-arm.
bool      safetyFaultLatched();
FaultCode safetyLastFault();
void      safetyClearFault();

// The one place "safe setpoint" is defined. Mutates args in place.
void safetyClampSetpoint(VapeMode& mode, float& volts, float& watts);

// Forced OFF path (watchdog bite / brown-out recovery / explicit fail-safe).
void safetyForceOff(FaultCode reason);
