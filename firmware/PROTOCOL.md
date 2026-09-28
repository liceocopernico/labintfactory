# LabInt wire protocol, version 1

The text protocol spoken by every LabDaemon board, whatever the microcontroller (Arduino AVR, ESP32, STM32, Teensy) and whatever the link (USB serial, Wi-Fi TCP, Bluetooth LE).

The PC side is implemented in `src/labdaemon/transports/wire.py`. `src/labdaemon/transports/simulated.py` implements the board side as an executable spec (`WireSimulator`), which is used in tests and by simulated devices. Where this document and the simulator disagree, fix one of them.

## 1. Terms

| Term | Meaning |
|---|---|
| Board | One physical unit and its connection. |
| Function | One instrument hosted by a board, such as `photometer` or `thermometer`. A combined board hosts several. |
| Host | The PC running LabDaemon. |

## 2. Lines

- ASCII text lines ending in `\n`. The host also accepts `\r\n`. A line is at most 160 bytes.
- UART boards default to 115 200 baud; USB CDC boards ignore the rate.
- Tokens are separated by spaces. A value containing spaces is written in double quotes. Inside quotes, `\"` and `\\` are escapes. Quotes may start inside a token: `ssid="Lab 2"`.
- Numbers always use `.` as the decimal separator, whatever the host's locale.

## 3. Commands

```
[function:]VERB [argument …]
```

- Verbs are upper case. Queries end with `?` (`ID?`, `LED?`).
- **Board-level** commands (§6) have no prefix.
- **Function** commands carry the function name as a prefix: `thermometer:READ?`. On a board with a single function the prefix is optional; the host always sends it.
- The host sends **one command at a time** and waits for its reply. The only exception is while a function runs an operation (after `BUSY`, §4): then the board still accepts commands for its *other* functions, plus `STOP`, `STATUS?` and `PING`.

## 4. Replies

Every command gets exactly one reply line:

| Reply | Meaning |
|---|---|
| `OK [key=value …]` | Done. Replies from a function include `fn=<function>`. |
| `BUSY fn=<function>` | Accepted; the operation continues and ends with an event (§5). |
| `ERR <code> <message>` | Refused or failed (§7). |

Payloads are `key=value` pairs. Their order doesn't matter, and the host ignores keys it doesn't know, so newer firmware stays compatible with older hosts.

**Timing.** A command must reply within **500 ms**. Anything slower must answer `BUSY` at once and finish with an event. While an operation is running, the host sends `STATUS?` about once a second; a board that stops answering is considered lost.

## 5. Events and debug lines

A board may send these lines at any time, between replies:

| Line | Meaning |
|---|---|
| `EVT BOOT proto=1` | The board (re)started. Boards that reset when the USB port opens send it first; the host waits for it (at most 3 s) when `PING` gets no answer. |
| `EVT DONE fn=… cmd=… [key=value …]` | An operation finished; the fields are its result. |
| `EVT STOPPED fn=… cmd=… [key=value …]` | An operation was stopped by `STOP`. |
| `EVT LIMIT fn=… side=… [key=value …]` | An operation hit a limit (for example a limit switch). |
| `EVT FAULT fn=… code=… msg=…` | A hardware fault. |
| `# anything` | A debug line: the host logs it and otherwise ignores it. |

`DONE`, `STOPPED`, `LIMIT` and `FAULT` end the function's current operation.

## 6. Board-level commands

Every firmware implements these (the LabInt library does it for you):

| Command | Reply | Notes |
|---|---|---|
| `ID?` | `OK proto=1 board=<type> fw=<version> serial=<id> name=<name> functions=<f1,f2> links=<usb,wifi,ble>` | Identification; the host creates one device per function. |
| `CMDS?` | `OK <function>=<VERB,VERB,…> …` | Conformance checks; completion in the raw console. |
| `PING` | `OK` | Liveness. |
| `STATUS?` | `OK <function>=idle\|busy …` | Heartbeat during operations. |
| `STOP` | `OK`, then `EVT STOPPED …` for each operation that was running | Stops every function; `<function>:STOP` stops one. Always accepted. |
| `RESET` | `OK` | Restores default settings. |
| `NAME <name>` | `OK` | Stores a friendly name, up to 24 characters. |
| `AUTH <token>` | `OK` or `ERR 8` | Required first on Wi-Fi and Bluetooth. |
| `NET?` | `OK ssid=… ip=… rssi=…` | Boards with Wi-Fi only. |
| `WIFI ssid=… psk=… [ip=… gw=…]`, `TOKEN?` | `OK`, `OK token=…` | Wi-Fi setup; accepted **over USB only**. |
| `<function>:HW?` | `OK <part>=<id> …` | Optional: the parts a function is built with (for example `sensor=tsl2591`). |

Boards without a hardware serial number (for example the Arduino Uno) generate a random one on first boot and keep it in EEPROM.

## 7. Error codes

| Code | Meaning |
|---|---|
| 1 | unknown command |
| 2 | bad argument |
| 3 | out of range |
| 4 | busy, or owned by another host |
| 5 | not ready (for example "not homed") |
| 6 | hardware fault |
| 7 | not supported |
| 8 | not authorised |
| 100+ | model-specific |

## 8. Versioning

`ID?` reports `proto=1`. New commands and new keys are additive and don't change the version; only a breaking change does. The host supports the current version and the previous one.

## 9. Function: `photometer` (TSL2591 + one LED)

Reference firmware: `firmware/sketches/photometer` (Arduino UNO R4 Minima). There is one LED, driven by the board's 12-bit DAC. Its colour depends on which LED is physically fitted: the board only remembers it, so that the host knows the valid power range and records it with every measurement.

| Command | Reply | Notes |
|---|---|---|
| `LED <power>` | `OK power=<n>` | Drive level 0–4095 on the DAC; 0 turns the LED off. The host limits the range per colour. |
| `LED?` | `OK power=<n> color=<colour>` | |
| `LEDCOLOR <colour>` | `OK color=<colour>` | Which LED is fitted: `red`, `orange`, `green` or `blue`. Kept in EEPROM. |
| `CFG <integration_ms> <gain>` | `OK int=<ms> gain=<g>` | Integration 100–600 ms in steps of 100; gain 1, 25, 428 or 9876. |
| `CFG?` | `OK int=<ms> gain=<g>` | |
| `READ <n>` | `BUSY`, then `EVT DONE … bb=<counts> ir=<counts> sat=<0\|1> n=<n>` | The mean of *n* conversions (1–15), full-spectrum and infrared counts. `sat=1` if any conversion reached full scale. `STOP` ends it early (`EVT STOPPED … n=<done>`). |
| `DIAG?` | `OK sensor=ok\|missing dac_bits=12` | Checks the sensor again. |
| `HW?` | `OK sensor=tsl2591\|none led=<colour>` | |

The host computes lux from the counts: `lux = (bb − ir)(1 − ir/bb) / (t·g/408)`. Full scale is 36 863 counts at 100 ms and 65 535 from 200 ms.

## 10. Example session

Recorded from the reference photometer (UNO R4 Minima):

```
→ PING                      ← OK
→ ID?                       ← OK proto=1 board=uno-r4-minima fw=2.0.0 serial=476B734F21FD name=LabInt-476B functions=photometer links=usb
→ photometer:HW?            ← OK fn=photometer sensor=tsl2591 led=red
→ photometer:LED 1850       ← OK fn=photometer power=1850
→ photometer:READ 3         ← BUSY fn=photometer
                            ← EVT DONE fn=photometer cmd=READ bb=598 ir=118 sat=0 n=3
→ photometer:LED 99999      ← ERR 3 out of range 0..4095
→ NOPE                      ← ERR 1 unknown command
→ photometer:SIM absorbance=0.3     (simulators only: set what is in the cuvette)
```

The UNO R4 does not restart when the port is opened, so no `EVT BOOT` arrives then. The host sends `PING` to find out when a board is ready, and still waits for `EVT BOOT` (at most 3 s) when a board does reset.
