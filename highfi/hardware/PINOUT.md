# HighFi — ESP32-S3 Pinout (reference)

Indicative GPIO map; adjust to your PCB. Keep strapping pins (0, 3, 45, 46) and
USB (19/20) clear of contention. Mirrors `firmware/include/config.h`.

## Audio (I2S → MAX98357A)
| Signal | GPIO |
|--------|-----:|
| I2S BCLK | 5 |
| I2S LRCLK/WS | 6 |
| I2S DOUT | 7 |
| Amp SD/enable | 8 |

## microSD (SDMMC 1-bit)
| Signal | GPIO |
|--------|-----:|
| CLK | 14 |
| CMD | 15 |
| D0 | 2 |
| (CD) card-detect | 1 |

## Vape / 510
| Signal | GPIO | Notes |
|--------|-----:|-------|
| Coil MOSFET gate (PWM) | 10 | LEDC PWM, **default 0 / OFF** |
| Coil current sense (INA alert) | 11 | short/over-current IRQ |
| Coil voltage/resistance ADC | 4 | divider on 510 pin |
| Coil NTC ADC | 9 | over-temp |

## Power / gauge (I²C bus A)
| Signal | GPIO |
|--------|-----:|
| SDA | 17 |
| SCL | 18 |
| Charger IRQ (BQ25895) | 21 |
| Cell NTC ADC | 16 |

## UI
| Signal | GPIO | Notes |
|--------|-----:|-------|
| OLED SDA/SCL | 17/18 | shares I²C bus A |
| Fire button | 12 | active-low, external pulldown to avoid boot fire |
| Play/Pause | 13 |
| Next | 42 |
| Prev | 41 |
| Vol+ / Vol− | 40 / 39 |
| Power/mode | 38 |
| WS2812 RGB (alt to OLED) | 48 |
| Haptic motor (opt) | 47 |

## Safety notes on pin choice
- **Fire GPIO (10)** drives the gate through a gate resistor + pulldown so the coil
  is guaranteed **OFF at reset/boot/brown-out** (never let a strapping pin fire).
- Current-sense IRQ (11) is a hardware fast-path: an over-current trips the gate low
  independent of firmware timing.
