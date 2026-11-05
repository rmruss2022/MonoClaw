# HighFi — Bill of Materials (reference design)

Prices are ballpark single-unit maker prices; verify at purchase.

## Core
| Qty | Part | Notes | ~$ |
|----:|------|-------|---:|
| 1 | ESP32-S3-WROOM-1-N16R8 | MCU module (16MB flash / 8MB PSRAM) | 4.50 |
| 1 | MAX98357A I2S amp | class-D, 3.2 W | 1.50 |
| 1 | 4 Ω 3 W micro speaker | 20–28 mm | 1.50 |
| 1 | microSD socket (push-push) | 1-bit SDMMC | 0.60 |
| 1 | 0.96" SSD1306 OLED (I²C) | 128×64 (or WS2812 ring alt) | 2.00 |

## Vape driver
| Qty | Part | Notes | ~$ |
|----:|------|-------|---:|
| 1 | 510 spring connector | brass, PCB-mount | 0.90 |
| 1 | N-ch MOSFET (low Rds, e.g. SIR158DP) | coil switch, PWM | 0.40 |
| 1 | Current-sense resistor (5 mΩ) + INA | wattage/short sense | 0.70 |
| 1 | NTC 10k (×2) | coil + cell temp | 0.20 |
| 1 | (opt) buck/boost for constant-watt | TPS63xxx | 1.80 |

## Power
| Qty | Part | Notes | ~$ |
|----:|------|-------|---:|
| 1 | 18650 Li-ion (or 18350 mini) | ~3000 mAh | 5.00 |
| 1 | BQ25895 USB-C charger (power-path) | (TP4056 ok for bench) | 1.80 |
| 1 | MAX17048 fuel gauge | I²C | 1.20 |
| 1 | Protection IC (DW01+FS8205) | if cell unprotected | 0.30 |
| 1 | TPS62840 buck (3.3 V) | MCU rail | 0.90 |
| 1 | USB-C receptacle | | 0.40 |

## UI / misc
| Qty | Part | Notes | ~$ |
|----:|------|-------|---:|
| 6 | tactile buttons | fire/play/next/prev/vol±/pwr | 0.60 |
| 1 | (opt) rotary encoder | replaces vol± | 0.80 |
| 1 | (opt) vibration motor | haptics | 0.40 |
| — | passives, PCB, enclosure | | 6.00 |

**Indicative total:** ~$38 in maker quantities (excludes cart). Volume BOM is far lower.

## Optional Bluetooth-audio-out (v2)
ESP32-S3 has **no Classic-BT A2DP**. To stream to BT speakers/headphones add one of:
- KCX_BT_EMITTER / BM83 BT-TX module fed from the I2S/line-out (~$3), **or**
- original ESP32 (WROVER) as a Classic-BT audio co-processor.

See [`SAFETY.md`](SAFETY.md) and [`PINOUT.md`](PINOUT.md).
