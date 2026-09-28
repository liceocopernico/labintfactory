# Firmware

Board-side code for LabDaemon. Every board speaks the LabInt wire protocol ([PROTOCOL.md](PROTOCOL.md)).

| Path | Contents |
|---|---|
| `lib/LabInt/` | The LabInt C++ library (Arduino core API): line parser, standard board commands, functions, long operations with `BUSY` and events, board serial number, a small settings store. |
| `sketches/photometer/` | Photometer 2.0 for the Arduino UNO R4 Minima: TSL2591 light sensor on I²C, one LED on the 12-bit DAC (pin A0). |

## Building and uploading

This needs `arduino-cli`. The copy inside Arduino IDE 2 works, or set `ARDUINO_CLI` to another one. Each board's core must be installed, for example `arduino-cli core install arduino:renesas_uno` for the UNO R4.

```bash
uv run python tools/firmware.py build photometer
uv run python tools/firmware.py upload photometer --port /dev/ttyACM0
```

`upload` also runs the conformance check afterwards:

```bash
uv run labdaemon firmware check /dev/ttyACM0   # 11 checks for the photometer
uv run labdaemon ports                         # what is on each USB serial port
```

The Arduino IDE also works: install `lib/LabInt` as a library (Sketch → Include Library → Add .ZIP Library, after zipping the folder), then open the sketch.

## Notes

- **Photometer hardware:** there is one LED, and its colour is whichever LED is fitted. `LEDCOLOR` only records it, in EEPROM, so the host knows the allowed power range and can store it with each measurement.
- **The TSL2591 driver is in the sketch**, not the Adafruit library. The Adafruit library waits inside each reading (up to 840 ms), which would break the 500 ms reply rule and stop `STOP` from working during a measurement.
- **Memory on small AVR boards:** a minimal LabInt sketch uses 1 287 bytes of the classic Uno's 2 048 bytes of RAM. It fits, but with a thin margin; moving the library's strings to flash is planned before AVR boards are used for real.
- **Previous firmware:** the photometer ran the single-character "… executed" protocol. Its source is in the separate `absorbance_photometer` repository (`firmware/firmware_2591`); flash it back from there if needed.
