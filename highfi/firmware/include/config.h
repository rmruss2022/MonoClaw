// HighFi — central compile-time configuration
// -----------------------------------------------------------------------------
// Single source of truth for pins, safety windows, and timing. Mirrors
// hardware/PINOUT.md and enforces the clamps from hardware/SAFETY.md / SPEC §5.
//
// SAFETY PHILOSOPHY (repeated across this firmware on purpose):
//   * The coil GPIO is owned EXCLUSIVELY by controlTask.
//   * Its power-on / reset / brown-out state is OFF (PWM duty 0).
//   * Every setpoint the app can send is CLAMPED here to a safe window.
//   * The network/app is untrusted input; it can only *request* fire.
// -----------------------------------------------------------------------------
#pragma once

#include <Arduino.h>

// ============================ Identity =======================================
#ifndef HIGHFI_FW_VERSION
#define HIGHFI_FW_VERSION "0.1.0"
#endif
#define HIGHFI_DEVICE_NAME "HighFi"
#define HIGHFI_MDNS_HOST   "highfi"   // -> highfi.local (SPEC §3.6)

// ============================ Pin map (PINOUT.md) ============================
// Keep strapping pins (0, 3, 45, 46) and USB (19/20) clear of contention.

// --- Audio: I2S -> MAX98357A class-D amp ---
#define PIN_I2S_BCLK    5
#define PIN_I2S_LRCLK   6    // word select
#define PIN_I2S_DOUT    7
#define PIN_AMP_SD      8    // amp shutdown/enable (HIGH = enabled)

// --- microSD (SDMMC, 1-bit) ---
#define PIN_SD_CLK      14
#define PIN_SD_CMD      15
#define PIN_SD_D0       2
#define PIN_SD_CD       1    // card-detect (active per socket; see sd_store)

// --- Vape / 510 coil driver ---
// The fire line drives a low-side N-MOSFET gate through a resistor + pulldown so
// the coil is guaranteed OFF at reset/boot/brown-out. NEVER move this to a
// strapping pin. See PINOUT.md "Safety notes on pin choice".
#define PIN_COIL_GATE   10   // LEDC PWM out to MOSFET gate. DEFAULT DUTY 0 / OFF.
#define PIN_COIL_IALERT 11   // INA over-current / short IRQ (hardware fast-path)
#define PIN_COIL_VSENSE 4    // ADC: 510-pin voltage divider -> resistance calc
#define PIN_COIL_NTC    9    // ADC: coil thermistor -> over-temp

// --- Power / gauge (I2C bus A, shared with OLED) ---
#define PIN_I2C_SDA     17
#define PIN_I2C_SCL     18
#define PIN_CHG_IRQ     21   // BQ25895 charger interrupt
#define PIN_CELL_NTC    16   // ADC: cell thermistor

// --- UI ---
// Fire button is active-low with an EXTERNAL pulldown to avoid boot-time fire.
#define PIN_BTN_FIRE    12
#define PIN_BTN_PLAY    13
#define PIN_BTN_NEXT    42
#define PIN_BTN_PREV    41
#define PIN_BTN_VOLUP   40
#define PIN_BTN_VOLDN   39
#define PIN_BTN_POWER   38   // power / mode / 5-click host
#define PIN_WS2812      48   // RGB status ring (alt to OLED)
#define PIN_HAPTIC      47   // vibration motor (optional)

// I2C addresses (bus A)
#define I2C_ADDR_OLED       0x3C   // SSD1306 128x64
#define I2C_ADDR_MAX17048   0x36   // fuel gauge
#define I2C_ADDR_BQ25895    0x6A   // charger

// ============================ Vape safety window ============================
// SPEC §3.3 / §5, SAFETY.md. These are the ONLY setpoints firmware will honor;
// app requests outside the window are clamped, never rejected-into-unsafe.
#define VAPE_VOLTS_MIN        2.5f    // V
#define VAPE_VOLTS_MAX        3.6f    // V
#define VAPE_WATTS_MIN        5.0f    // W
#define VAPE_WATTS_MAX        15.0f   // W
#define VAPE_VOLTS_DEFAULT    3.2f
#define VAPE_WATTS_DEFAULT    9.0f

// Coil resistance interlocks (ohms)
#define COIL_OHMS_SHORT       0.15f   // < this => short-circuit fault + latch
#define COIL_OHMS_OPEN        3.0f    // > this (or open) => no-atomizer lockout
#define COIL_OHMS_VALID_MIN   0.15f   // inclusive-usable band edges (readability)
#define COIL_OHMS_VALID_MAX   3.0f

// Temperature interlocks (deg C)
#define COIL_TEMP_MAX_C       230.0f  // coil NTC over-temp cutoff
#define CELL_TEMP_MAX_C       60.0f   // cell NTC over-temp cutoff
#define COIL_TEMP_COOLDOWN_C  180.0f  // must fall below this to re-arm after over-temp

// Current interlock (amps) — soft firmware limit; hardware INA IRQ is the fast path
#define COIL_CURRENT_MAX_A    8.0f

// Timing
#define FIRE_MAX_MS           10000   // hard 10 s cutoff (SPEC §5.1)
#define FIRE_COOLDOWN_MS      1500    // enforced rest after a full-length fire
#define AUTO_LOCK_MS          120000  // re-lock after 2 min idle (SAFETY.md §6)
#define COMMS_LOSS_MS         3000    // no WS ping within this => request fire OFF

// ============================ LEDC (coil gate PWM) ==========================
#define COIL_LEDC_CHANNEL     0
#define COIL_LEDC_FREQ_HZ     20000   // 20 kHz: above audio band, easy gate drive
#define COIL_LEDC_RES_BITS    10      // 0..1023 duty
#define COIL_LEDC_DUTY_MAX    ((1 << COIL_LEDC_RES_BITS) - 1)
#define COIL_LEDC_DUTY_OFF    0       // <-- the safe default, everywhere

// Sense scaling (board-specific; calibrate per unit). Documented so the math is
// honest rather than magic numbers buried in coil_control.cpp.
#define VSENSE_DIVIDER_RATIO  2.0f    // Vpin = Vcoil / ratio
#define ISENSE_SHUNT_OHMS     0.005f  // 5 mR sense resistor (BOM)
#define ISENSE_GAIN           50.0f   // INA gain
#define ADC_VREF              3.3f
#define ADC_MAX_COUNTS        4095.0f // 12-bit

// ============================ RTOS task model (ARCHITECTURE) ================
// core / priority / stack — controlTask is the highest-priority, coil-owning task.
#define TASK_CONTROL_CORE     0
#define TASK_CONTROL_PRIO     (configMAX_PRIORITIES - 1)   // highest
#define TASK_CONTROL_STACK    4096
#define TASK_CONTROL_PERIOD_MS 5      // 200 Hz fire/safety loop

#define TASK_AUDIO_CORE       1
#define TASK_AUDIO_PRIO       (configMAX_PRIORITIES - 2)   // high; must not underrun
#define TASK_AUDIO_STACK      8192

#define TASK_NET_CORE         0
#define TASK_NET_PRIO         3        // normal
#define TASK_NET_STACK        8192

#define TASK_UI_CORE          0
#define TASK_UI_PRIO          1        // low
#define TASK_UI_STACK         4096
#define TASK_UI_PERIOD_MS     50       // 20 Hz render

// Watchdog: controlTask feeds it every loop; a bite forces coil OFF on reset.
#define WDT_TIMEOUT_S         3

// Buttons
#define BTN_DEBOUNCE_MS       25
#define BTN_MULTICLICK_MS     600      // window for the 5-click lock gesture
#define BTN_LOCK_CLICKS       5

// Audio defaults
#define AUDIO_VOLUME_DEFAULT  40       // 0..100
#define SD_MUSIC_DIR          "/music"
#define FLASH_MUSIC_DIR       "/music" // LittleFS fallback tracks
#define CONFIG_PATH           "/config.json"  // on LittleFS
