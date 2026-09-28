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
| `EVT BOOT proto=1` | The board (re)started. Boards that reset when the USB port opens send it first, and the host waits for it (at most 3 s). |
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

## 9. Function: `photometer` (TSL2591 + LEDs)

| Command | Reply | Notes |
|---|---|---|
| `LED <colour> <power>` | `OK` | Colours `red` (power 100–4000), `orange` (780–850), `green` (780–900), `blue` (780–850). Power 0 turns the LED off. |
| `LED?` | `OK color=<colour> power=<n>` | |
| `CFG <integration_ms> <gain>` | `OK int=<ms> gain=<g>` | Integration 100–600 ms in steps of 100; gain 1, 25, 428 or 9876. |
| `CFG?` | `OK int=<ms> gain=<g>` | |
| `READ <n>` | `OK bb=<counts> ir=<counts> sat=<0\|1>` | The mean of *n* conversions (1–15), full-spectrum and infrared counts. If *n* × integration time exceeds the 500 ms reply limit, the firmware answers `BUSY` and sends the same fields in `EVT DONE`. |
| `HW?` | `OK sensor=tsl2591 leds=<id>` | |

The host computes lux from the counts: `lux = (bb − ir)(1 − ir/bb) / (t·g/408)`.

## 10. Example session

```
← EVT BOOT proto=1
→ ID?                       ← OK proto=1 board=uno fw=2.0.0 serial=7F3A91C2 name=Bench-3 functions=photometer links=usb
→ photometer:LED red 1850   ← OK fn=photometer
→ photometer:READ 3         ← OK fn=photometer bb=5691 ir=1899 sat=0
→ photometer:LED green 5000 ← ERR 3 power out of range 780..900
→ photometer:SIM absorbance=0.3     (simulators only: set what is in the cuvette)
```
