// HighFi — safety implementation. The coil's conscience.
#include "vape/safety.h"
#include "vape/coil_control.h"
#include "config.h"

// Lock: ships LOCKED (SAFETY.md §6).
static volatile bool s_locked = true;

// Latched fault (must be explicitly cleared, e.g. by removing the cart).
static FaultCode s_latched = FaultCode::NONE;

// Over-temp cool-down: once tripped, block until coil falls below the re-arm.
static bool s_overTempCooling = false;

// Post-fire enforced rest window.
static uint32_t s_cooldownUntilMs = 0;

// Auto-relock timer.
static uint32_t s_lastActivityMs = 0;

const char* faultCodeStr(FaultCode f) {
    switch (f) {
        case FaultCode::NONE:         return "none";
        case FaultCode::LOCKED:       return "locked";
        case FaultCode::NO_ATOMIZER:  return "no-atomizer";
        case FaultCode::SHORT:        return "short";
        case FaultCode::OVER_TEMP:    return "over-temp";
        case FaultCode::OVER_CURRENT: return "over-current";
        case FaultCode::TIMEOUT:      return "timeout";
        case FaultCode::COOLDOWN:     return "cooldown";
        case FaultCode::COMMS_LOSS:   return "comms-loss";
        case FaultCode::WATCHDOG:     return "watchdog";
        default:                      return "unknown";
    }
}

void safetyInit() {
    s_locked          = true;   // boot locked, always
    s_latched         = FaultCode::NONE;
    s_overTempCooling = false;
    s_cooldownUntilMs = 0;
    s_lastActivityMs  = millis();
}

// ---------------------------------------------------------------- verdict ----
SafetyVerdict safetyEvaluate(const SafetyInputs& in) {
    const uint32_t now = millis();

    // 0) A previously latched hard fault (e.g. short) wins until cleared.
    if (s_latched != FaultCode::NONE) {
        // Auto-clear no-atomizer/temp latches once conditions are safe again;
        // SHORT stays latched until the cart is physically removed (open reading).
        if (s_latched == FaultCode::SHORT && (!isfinite(in.coilOhms) || in.coilOhms > COIL_OHMS_OPEN)) {
            s_latched = FaultCode::NONE;
        } else {
            coilOff();
            return { false, s_latched };
        }
    }

    // 1) Lock — device must be unlocked to fire (physical 5-click).
    if (s_locked) return { false, FaultCode::LOCKED };

    // 2) No request => trivially off (not a fault).
    if (!in.fireRequested) {
        return { false, FaultCode::NONE };
    }

    // 3) Comms loss with a network-originated request => fail safe OFF.
    //    (controlTask only passes commsOk=false once the WS ping window lapses.)
    if (!in.commsOk) {
        return { false, FaultCode::COMMS_LOSS };
    }

    // 4) Short circuit — latch and refuse. Hardware INA IRQ also cuts the gate.
    if (isfinite(in.coilOhms) && in.coilOhms < COIL_OHMS_SHORT) {
        s_latched = FaultCode::SHORT;
        coilOff();
        return { false, FaultCode::SHORT };
    }

    // 5) No atomizer — open or absurdly high resistance.
    if (!isfinite(in.coilOhms) || in.coilOhms > COIL_OHMS_OPEN || !in.cartPresent) {
        return { false, FaultCode::NO_ATOMIZER };
    }

    // 6) Over-current (soft limit).
    if (in.coilCurrentA > COIL_CURRENT_MAX_A) {
        return { false, FaultCode::OVER_CURRENT };
    }

    // 7) Over-temperature (coil or cell), with hysteretic re-arm.
    if (in.coilTempC > COIL_TEMP_MAX_C || in.cellTempC > CELL_TEMP_MAX_C) {
        s_overTempCooling = true;
        return { false, FaultCode::OVER_TEMP };
    }
    if (s_overTempCooling) {
        if (in.coilTempC > COIL_TEMP_COOLDOWN_C) {
            return { false, FaultCode::OVER_TEMP };   // still too hot to re-arm
        }
        s_overTempCooling = false;                    // cooled enough; clear
    }

    // 8) Enforced rest window after a full-length fire.
    if ((int32_t)(s_cooldownUntilMs - now) > 0) {
        return { false, FaultCode::COOLDOWN };
    }

    // 9) 10 s hard cutoff. On hitting it, arm the rest window so the user must
    //    release and wait — no infinite re-fire by holding the button.
    if (in.fireElapsedMs >= FIRE_MAX_MS) {
        s_cooldownUntilMs = now + FIRE_COOLDOWN_MS;
        return { false, FaultCode::TIMEOUT };
    }

    // All interlocks satisfied.
    return { true, FaultCode::NONE };
}

// ------------------------------------------------------------------ lock -----
bool safetyIsLocked() { return s_locked; }

void safetyLock() {
    s_locked = true;
    coilRequestFire(false, FireSource::BUTTON);
    coilRequestFire(false, FireSource::NET);
    coilOff();
}

void safetyUnlock() {
    // Only reachable from the physical 5-click path (buttons.cpp). The network
    // command handler deliberately does NOT call this.
    s_locked = false;
    s_lastActivityMs = millis();
}

void safetyNoteActivity() { s_lastActivityMs = millis(); }

void safetyServiceAutoLock() {
    if (!s_locked && (millis() - s_lastActivityMs) > AUTO_LOCK_MS) {
        safetyLock();
    }
}

// ------------------------------------------------------------------ fault ----
bool      safetyFaultLatched() { return s_latched != FaultCode::NONE; }
FaultCode safetyLastFault()    { return s_latched; }
void      safetyClearFault()   { s_latched = FaultCode::NONE; s_overTempCooling = false; }

// ------------------------------------------------------------------ clamp ----
void safetyClampSetpoint(VapeMode& mode, float& volts, float& watts) {
    // mode passes through (voltage|watts); values clamped to the SPEC window.
    volts = constrain(volts, VAPE_VOLTS_MIN, VAPE_VOLTS_MAX);
    watts = constrain(watts, VAPE_WATTS_MIN, VAPE_WATTS_MAX);
    (void)mode;
}

// --------------------------------------------------------------- force off ---
void safetyForceOff(FaultCode reason) {
    coilRequestFire(false, FireSource::BUTTON);
    coilRequestFire(false, FireSource::NET);
    coilOff();
    if (reason == FaultCode::SHORT || reason == FaultCode::WATCHDOG) {
        s_latched = reason;   // require explicit clear for the serious ones
    }
}
