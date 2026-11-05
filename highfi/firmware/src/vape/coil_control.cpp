// HighFi — coil_control implementation.
#include "vape/coil_control.h"
#include "config.h"

// Fire-request flags, one per source. volatile + single-writer-per-flag keeps
// this lock-free; controlTask reads the OR of them.
static volatile bool s_reqButton = false;
static volatile bool s_reqNet     = false;

// Current (already-clamped) setpoint.
static VapeMode s_mode  = VapeMode::VOLTAGE;
static float    s_volts = VAPE_VOLTS_DEFAULT;
static float    s_watts = VAPE_WATTS_DEFAULT;

static bool s_energized = false;

// --------------------------------------------------------------------- init --
void coilInit() {
    // Gate PWM: attach at duty 0 (OFF) BEFORE anything else can touch it.
    // Arduino-ESP32 v3 LEDC API. On boot the pin also has an external pulldown.
    ledcAttachChannel(PIN_COIL_GATE, COIL_LEDC_FREQ_HZ, COIL_LEDC_RES_BITS, COIL_LEDC_CHANNEL);
    ledcWrite(PIN_COIL_GATE, COIL_LEDC_DUTY_OFF);
    s_energized = false;

    // ADC sense pins.
    analogReadResolution(12);
    pinMode(PIN_COIL_VSENSE, INPUT);
    pinMode(PIN_COIL_NTC,    INPUT);

    // Over-current / short IRQ from the INA is a hardware fast-path; we also wire
    // an ISR that slams the gate low without waiting on the control loop.
    pinMode(PIN_COIL_IALERT, INPUT_PULLUP);
    // attachInterrupt(PIN_COIL_IALERT, coilOverCurrentISR, FALLING);  // see below
}

// Hard, ISR-safe cut. (Registered in coilInit when the INA alert is populated.)
void IRAM_ATTR coilOverCurrentISR() {
    ledcWrite(PIN_COIL_GATE, COIL_LEDC_DUTY_OFF);
    s_energized = false;
    s_reqButton = false;
    s_reqNet    = false;
}

// ------------------------------------------------------------------ request --
void coilRequestFire(bool on, FireSource src) {
    if (src == FireSource::BUTTON) s_reqButton = on;
    else                           s_reqNet    = on;
}

bool coilFireRequested() { return s_reqButton || s_reqNet; }

void coilClearRequest(FireSource src) {
    if (src == FireSource::BUTTON) s_reqButton = false;
    else                           s_reqNet    = false;
}

// ----------------------------------------------------------------- setpoint --
void coilSetSetpoint(VapeMode mode, float volts, float watts) {
    // Defensive re-clamp: this module refuses to hold an out-of-window setpoint
    // even if a caller forgot to run it through safety.
    s_mode  = mode;
    s_volts = constrain(volts, VAPE_VOLTS_MIN, VAPE_VOLTS_MAX);
    s_watts = constrain(watts, VAPE_WATTS_MIN, VAPE_WATTS_MAX);
}

// ------------------------------------------------------------------- sensing --
// Read the 510 pin divider, derive coil resistance from the small "probe" bias
// present when idle (real hardware pulses a tiny known current to measure R).
// Here we present a physically-consistent model; swap in the calibrated read.
CoilSense coilReadSense() {
    CoilSense s{};
    s.valid = true;

    int vcounts = analogRead(PIN_COIL_VSENSE);
    int tcounts = analogRead(PIN_COIL_NTC);

    // Coil voltage at the 510 pin.
    float vpin  = (vcounts / ADC_MAX_COUNTS) * ADC_VREF;
    float vcoil = vpin * VSENSE_DIVIDER_RATIO;

    // Current via the INA'd shunt (only meaningful while energized). We model the
    // measured drop; on real HW this is a second ADC / INA219 read.
    float ishunt_v = (vcounts / ADC_MAX_COUNTS) * ADC_VREF;   // placeholder tap
    s.currentA = s_energized ? (ishunt_v / (ISENSE_SHUNT_OHMS * ISENSE_GAIN)) : 0.0f;

    // Resistance: V / I when firing; when idle we rely on the probe measurement.
    if (s.currentA > 0.05f) {
        s.ohms = vcoil / s.currentA;
    } else {
        // Idle probe: map the divider reading to an equivalent resistance. An
        // open 510 (no cart) reads near-rail -> large ohms -> no-atomizer.
        float frac = vcounts / ADC_MAX_COUNTS;
        s.ohms = (frac > 0.98f) ? INFINITY : (0.1f + frac * 4.0f);
    }

    // Coil NTC -> temperature (Steinhart-Hart in a real driver; linearized here).
    float tfrac = tcounts / ADC_MAX_COUNTS;
    s.coilTempC = 20.0f + tfrac * 240.0f;

    return s;
}

// ------------------------------------------------------------------- drive ---
void coilEnergize(const CoilSense& sense) {
    // Compute the target coil voltage:
    //   voltage mode -> setpoint directly.
    //   watts mode   -> V = sqrt(P * R) from the measured resistance.
    float targetV;
    if (s_mode == VapeMode::WATTS) {
        float r = (isfinite(sense.ohms) && sense.ohms > COIL_OHMS_SHORT) ? sense.ohms : 1.0f;
        targetV = sqrtf(s_watts * r);
    } else {
        targetV = s_volts;
    }
    targetV = constrain(targetV, 0.0f, VAPE_VOLTS_MAX);

    // PWM duty = fraction of VBAT needed to average targetV across the coil.
    // Use the measured battery voltage from AppState (falls back to a nominal).
    float vbat = 3.7f;
    if (stateLock(pdMS_TO_TICKS(2))) { vbat = g_state.power.voltage > 2.5f ? g_state.power.voltage : 3.7f; stateUnlock(); }

    float dutyFrac = constrain(targetV / vbat, 0.0f, 1.0f);
    uint32_t duty  = (uint32_t)(dutyFrac * COIL_LEDC_DUTY_MAX);

    ledcWrite(PIN_COIL_GATE, duty);
    s_energized = (duty > 0);
}

void coilOff() {
    ledcWrite(PIN_COIL_GATE, COIL_LEDC_DUTY_OFF);
    s_energized = false;
}

bool coilIsEnergized() { return s_energized; }
