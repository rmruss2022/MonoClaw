// HighFi — coil_control: the 510 coil driver primitives.
// -----------------------------------------------------------------------------
// Owns the LEDC PWM gate output and the ADC sense channels. It NEVER fires on
// its own: requestFire() only records intent. The coil is energized solely by
// controlTask, and only after src/vape/safety.* returns allowFire == true.
//
// Layering:
//   ws_server / buttons  --requestFire()-->  [flag]
//   controlTask (tick):  read sense -> safety verdict -> energize() or off()
// -----------------------------------------------------------------------------
#pragma once

#include <Arduino.h>
#include "app_state.h"   // VapeMode

// Where a fire request originated. Kept separate so comms loss can drop only the
// network request without cancelling a physical button hold, and vice-versa.
enum class FireSource : uint8_t { BUTTON, NET };

// One coherent read of the coil's electrical/thermal state.
struct CoilSense {
    float ohms;      // measured coil resistance (open -> large / INFINITY)
    float currentA;  // measured coil current while energized (~0 when off)
    float coilTempC; // coil NTC
    bool  valid;     // false if a read glitched
};

void coilInit();                                  // configures LEDC (duty 0) + ADC

// Request / release fire from a given source. Thread-safe (atomic flags).
void coilRequestFire(bool on, FireSource src);
bool coilFireRequested();                          // any source active?
void coilClearRequest(FireSource src);             // e.g. comms loss -> drop NET

// Setpoint (already clamped by safety before it reaches here).
void coilSetSetpoint(VapeMode mode, float volts, float watts);

// Sensing. Cheap enough to call every control tick.
CoilSense coilReadSense();

// Drive / stop. energize() computes the LEDC duty for the current setpoint given
// the measured resistance, then applies it. off() forces duty 0 immediately.
// These are called ONLY by controlTask, gated by safety.
void coilEnergize(const CoilSense& sense);
void coilOff();
bool coilIsEnergized();
