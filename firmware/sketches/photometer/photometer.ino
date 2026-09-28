// LabDaemon photometer firmware 2.0 — Arduino UNO R4 Minima, TSL2591 light sensor, one LED on the DAC.
//
// Function "photometer" (firmware/PROTOCOL.md §9):
//   LED <0..4095>        LED drive level on the 12-bit DAC (pin A0); 0 = off
//   LED?                 -> power=… color=…
//   LEDCOLOR <colour>    which LED is fitted: red | orange | green | blue (kept in EEPROM)
//   CFG <ms> <gain>      integration 100..600 ms (steps of 100), gain 1 | 25 | 428 | 9876
//   CFG?                 -> int=… gain=…
//   READ <n>             BUSY, then EVT DONE bb=… ir=… sat=0|1 n=…: mean of n conversions
//   DIAG?                -> sensor=ok|missing
//
// The TSL2591 is driven directly over I2C without blocking, so the board always answers
// within the protocol's 500 ms and STOP works during a measurement.
#include <LabInt.h>
#include <Wire.h>

LabInt board("2.0.0");
LabInt::Function& photo = board.function("photometer");

// ── TSL2591 ──────────────────────────────────────────────────────────────────────────────────────
namespace tsl2591 {
const uint8_t ADDRESS = 0x29;
const uint8_t COMMAND = 0xA0;  // command bit + normal transaction
const uint8_t REG_ENABLE = 0x00, REG_CONTROL = 0x01, REG_ID = 0x12, REG_STATUS = 0x13, REG_C0DATAL = 0x14;
const uint8_t PON = 0x01, AEN = 0x02, DEVICE_ID = 0x50;

bool write8(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(ADDRESS);
  Wire.write(COMMAND | reg);
  Wire.write(value);
  return Wire.endTransmission() == 0;
}

bool read(uint8_t reg, uint8_t* out, uint8_t n) {
  Wire.beginTransmission(ADDRESS);
  Wire.write(COMMAND | reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(ADDRESS, n) != n) return false;
  for (uint8_t i = 0; i < n; ++i) out[i] = Wire.read();
  return true;
}

bool present() {
  uint8_t id = 0;
  return read(REG_ID, &id, 1) && id == DEVICE_ID;
}

bool configure(uint8_t atime, uint8_t again) { return write8(REG_CONTROL, (uint8_t)((again << 4) | atime)); }

bool start() { return write8(REG_ENABLE, PON) && write8(REG_ENABLE, PON | AEN); }  // restart integration

int ready() {  // 1 = a full integration finished, 0 = not yet, -1 = I2C error
  uint8_t status = 0;
  if (!read(REG_STATUS, &status, 1)) return -1;
  return status & 0x01;
}

bool counts(uint16_t& c0, uint16_t& c1) {
  uint8_t b[4];
  if (!read(REG_C0DATAL, b, 4)) return false;
  c0 = (uint16_t)(b[1] << 8 | b[0]);
  c1 = (uint16_t)(b[3] << 8 | b[2]);
  return true;
}

void powerOff() { write8(REG_ENABLE, 0x00); }
}  // namespace tsl2591

// ── state ────────────────────────────────────────────────────────────────────────────────────────
const char* const COLORS[] = {"red", "orange", "green", "blue"};
const uint8_t NCOLORS = 4;
const uint16_t GAINS[] = {1, 25, 428, 9876};
const uint8_t SETTING_COLOR = 0;

bool sensorOk = false;
uint16_t ledPower = 0;
uint8_t colorIndex = 0;
uint8_t atime = 0;  // 0..5 → 100..600 ms
uint8_t again = 1;  // 0..3 → gain 1, 25, 428, 9876

struct Reading {
  bool active = false;
  uint8_t wanted = 0, done = 0;
  uint32_t sum0 = 0, sum1 = 0;
  bool saturated = false;
  unsigned long started = 0;
} reading;

uint16_t integrationMs() { return (atime + 1) * 100; }
uint16_t fullScale() { return atime == 0 ? 36863 : 65535; }

void applyLed() { analogWrite(DAC, ledPower); }

// ── commands ─────────────────────────────────────────────────────────────────────────────────────
void cmdLed(LabInt::Request& rq) {
  long power = rq.intArg(0, -1, 0, 4095);
  if (!rq) return;
  if (power < 0) return rq.fail(LabInt::ERR_ARGUMENT, "power required");
  ledPower = (uint16_t)power;
  applyLed();
  rq.ok().kv("power", (long)ledPower).send();
}

void cmdLedQuery(LabInt::Request& rq) {
  rq.ok().kv("power", (long)ledPower).kv("color", COLORS[colorIndex]).send();
}

void cmdLedColor(LabInt::Request& rq) {
  const char* name = rq.arg(0);
  for (uint8_t i = 0; name && i < NCOLORS; ++i) {
    if (strcmp(name, COLORS[i]) == 0) {
      colorIndex = i;
      board.setSetting(SETTING_COLOR, i);
      photo.hw("led", COLORS[i]);
      rq.ok().kv("color", COLORS[i]).send();
      return;
    }
  }
  rq.fail(LabInt::ERR_ARGUMENT, "colour must be red, orange, green or blue");
}

void cmdCfg(LabInt::Request& rq) {
  long ms = rq.intArg(0, integrationMs(), 100, 600);
  long gain = rq.intArg(1, GAINS[again], 1, 9876);
  if (!rq) return;
  if (ms % 100) return rq.fail(LabInt::ERR_RANGE, "integration in steps of 100 ms");
  int8_t g = -1;
  for (uint8_t i = 0; i < 4; ++i)
    if (GAINS[i] == gain) g = i;
  if (g < 0) return rq.fail(LabInt::ERR_RANGE, "gain must be 1, 25, 428 or 9876");
  atime = (uint8_t)(ms / 100 - 1);
  again = (uint8_t)g;
  if (sensorOk && !tsl2591::configure(atime, again)) return rq.fail(LabInt::ERR_HARDWARE, "sensor not answering");
  rq.ok().kv("int", (long)integrationMs()).kv("gain", (long)GAINS[again]).send();
}

void cmdCfgQuery(LabInt::Request& rq) {
  rq.ok().kv("int", (long)integrationMs()).kv("gain", (long)GAINS[again]).send();
}

void cmdRead(LabInt::Request& rq) {
  long n = rq.intArg(0, 1, 1, 15);
  if (!rq) return;
  if (!sensorOk) return rq.fail(LabInt::ERR_HARDWARE, "TSL2591 not found");
  if (!tsl2591::configure(atime, again) || !tsl2591::start())
    return rq.fail(LabInt::ERR_HARDWARE, "sensor not answering");
  reading = Reading();
  reading.active = true;
  reading.wanted = (uint8_t)n;
  reading.started = millis();
  rq.busy();
}

void cmdDiag(LabInt::Request& rq) {
  sensorOk = tsl2591::present();
  rq.ok().kv("sensor", sensorOk ? "ok" : "missing").kv("dac_bits", 12L).send();
}

void onStop(LabInt::Line& stopped) {
  reading.active = false;
  tsl2591::powerOff();
  stopped.kv("n", (long)reading.done);
}

void onReset() {
  reading.active = false;
  tsl2591::powerOff();
  ledPower = 0;
  applyLed();
  atime = 0;
  again = 1;
  if (sensorOk) tsl2591::configure(atime, again);
}

// ── measurement state machine ────────────────────────────────────────────────────────────────────
void updateReading() {
  if (!reading.active) return;
  int state = tsl2591::ready();
  if (state == 0) {
    if (millis() - reading.started > 2UL * integrationMs() + 250) {
      reading.active = false;
      tsl2591::powerOff();
      photo.fault(LabInt::ERR_HARDWARE, "sensor timeout");
    }
    return;
  }
  uint16_t c0 = 0, c1 = 0;
  if (state < 0 || !tsl2591::counts(c0, c1)) {
    reading.active = false;
    photo.fault(LabInt::ERR_HARDWARE, "I2C error");
    return;
  }
  reading.sum0 += c0;
  reading.sum1 += c1;
  if (c0 >= fullScale() || c1 >= fullScale()) reading.saturated = true;
  reading.done++;
  if (reading.done < reading.wanted) {
    tsl2591::start();
    reading.started = millis();
    return;
  }
  reading.active = false;
  tsl2591::powerOff();
  photo.done()
      .kv("bb", (long)((reading.sum0 + reading.wanted / 2) / reading.wanted))
      .kv("ir", (long)((reading.sum1 + reading.wanted / 2) / reading.wanted))
      .kv("sat", reading.saturated)
      .kv("n", (long)reading.done)
      .send();
}

void setup() {
  Serial.begin(115200);
  Wire.begin();
  analogWriteResolution(12);
  applyLed();  // LED off until the host sets a power

  colorIndex = board.setting(SETTING_COLOR, 0);
  if (colorIndex >= NCOLORS) colorIndex = 0;
  sensorOk = tsl2591::present();
  if (sensorOk) {
    tsl2591::configure(atime, again);
    tsl2591::powerOff();
  }

  photo.on("LED", cmdLed).on("LED?", cmdLedQuery).on("LEDCOLOR", cmdLedColor)
      .on("CFG", cmdCfg).on("CFG?", cmdCfgQuery).on("READ", cmdRead).on("DIAG?", cmdDiag)
      .hw("sensor", sensorOk ? "tsl2591" : "none").hw("led", COLORS[colorIndex])
      .onStop(onStop).onReset(onReset);
  board.begin(Serial);
  if (!sensorOk) board.debug("TSL2591 not found at I2C address 0x29");
}

void loop() {
  board.poll();
  updateReading();
}
