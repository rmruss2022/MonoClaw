# HighFi — Safety & Legal

**Read this before building, wiring, or powering anything.**

HighFi combines two genuinely hazardous things: a **lithium-ion cell** capable of
high discharge current, and a **heating element** (the 510 coil). Mistakes cause
burns, fires, venting cells, or worse. This repository is an **experimental maker
reference design**. It is **not** a certified consumer product.

## Hard firmware interlocks (must all be present)
These are enforced in `controlTask` / `vape/safety`, independent of the app or network:

1. **10-second hard cutoff.** No single fire event may exceed 10 s. Timer lives in
   the high-priority control task, not the network task.
2. **No-atomizer lockout.** If measured coil resistance is open or > ~3 Ω, fire is
   blocked (nothing connected / bad contact).
3. **Short-circuit cutoff.** Coil < ~0.15 Ω ⇒ block + latch fault. A hardware
   current-sense IRQ also pulls the gate low without waiting on firmware.
4. **Over-temperature cutoff.** Coil or cell NTC over threshold ⇒ stop, cool-down.
5. **Battery protection.** Dedicated protection IC + fuel gauge for
   over-charge / over-discharge / over-current / cell-short. Never rely on firmware
   alone for cell safety.
6. **5-click lock.** Device boots **locked**; fire is disabled until the user
   unlocks. Auto-relocks after inactivity.
7. **Fail-safe default.** On reset, brown-out, fault latch, watchdog bite, or loss
   of app/UI comms, the coil GPIO defaults **OFF**. Firmware clamps every app-sent
   setpoint to the safe window; the app is treated as untrusted input.
8. **Independent watchdogs.** Software safety watchdog + hardware WDT; either firing
   forces coil OFF.

## Hardware guidance
- Use a quality **protected** or well-specced 18650/18350 from a reputable cell; match
  continuous-discharge rating to coil load with margin.
- Gate driver with pulldown so the MOSFET is **off at power-on / during boot**
  (avoid strapping-pin GPIOs for the fire line).
- Thermally isolate the coil path from the cell and the PCB.
- Fuse / current limit the coil branch.
- USB-C charging via a proper single-cell charger with power-path; do not charge
  unattended during bring-up.

## Legal
- **Not FDA-cleared.** In the US, nicotine vaping hardware requires FDA PMTA
  authorization to be marketed; this design is not authorized and is not for sale.
- **Cannabis hardware is state-regulated.** Legality of use, sale, and possession
  varies by jurisdiction. You are responsible for compliance.
- Intended, if used at all, for **adults of legal age** with **legal** carts where
  permitted. Aromatherapy/essential-oil carts are a non-regulated alternative for
  demos.
- No warranty. Build and operate at your own risk.

If any of the interlocks above are not implemented and verified, **do not attach a
cart or fire the coil.** Bench-test the audio and app paths first with the coil
driver disconnected.
