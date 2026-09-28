// LabDaemon photometer firmware 2.0.1 — Arduino UNO R4 Minima, TSL2591 light sensor, one LED on the DAC.
//
// Function "photometer" (firmware/PROTOCOL.md §9):
//   LED <0..4095>        LED drive level on the 12-bit DAC (pin A0); 0 = off
//   LED?                 -> power=… color=…
//   LEDCOLOR <colour>    which LED is fitted: red | orange | green | blue (kept in EEPROM)
//   CFG <ms> <gain>      integration 100..600 ms (steps of 100), gain 1 | 25 | 428 | 9876
//   CFG?                 -> int=… gain=…
//   READ <n>             BUSY, then EVT DONE bb=… ir=… sat=0|1 n=…: mean of n conversions
//   DIAG?                -> sensor=ok|missing i2c_errors=… recoveries=…
//
// The TSL2591 is driven directly over I2C without blocking, so the board always answers
// within the protocol's 500 ms and STOP works during a measurement.
//
// I2C robustness (2.0.1): on the UNO R4 core, a Wire transaction that times out is never aborted,
// and every later one then fails until the board is reset. So the firmware polls the sensor only
// as often as needed, and after any failed transaction it restarts Wire, clocks the bus free,
// reconfigures the sensor and retries before reporting a fault.
#include <LabInt.h>
#include <Wire.h>

LabInt board("2.0.1");
LabInt::Function& photo = board.function("photometer");

// ── TSL2591 ──────────────────────────────────────────────────────────────────────────────────────
namespace tsl2591 {
const uint8_t ADDRESS = 0x29;
const uint8_t COMMAND = 0xA0;  // command bit + normal transaction
const uint8_t REG_ENABLE = 0x00, REG_CONTROL = 0x01, REG_ID = 0x12, REG_STATUS = 0x13, REG_C0DATAL = 0x14;
const uint8_t PON = 0x01, AEN = 0x02, DEVICE_ID = 0x50;

unsigned long errors = 0, recoveries = 0;

bool write8(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(ADDRESS);
  Wire.write(COMMAND | reg);
  Wire.write(value);
  if (Wire.endTransmission() == 0) return true;
  errors++;
  return false;
}

bool read(uint8_t reg, uint8_t* out, uint8_t n) {
  Wire.beginTransmission(ADDRESS);
  Wire.write(COMMAND | reg);
  if (Wire.endTransmission(false) != 0 || Wire.requestFrom(ADDRESS, n) != n) {
    errors++;
    return false;
  }
  for (uint8_t i = 0; i < n; ++i) out[i] = Wire.read();
  return true;
}

void beginBus() {
  Wire.begin();
  Wire.setClock(100000);
  Wire.setWireTimeout(20000);  // 20 ms: a TSL2591 transaction takes well under 1 ms
}

// Restart Wire and free the bus: if the sensor was cut off in the middle of a byte it may hold SDA
// low; up to nine SCL pulses let it finish, then a STOP condition resets both sides.
void recover() {
  recoveries++;
  Wire.end();
  pinMode(SDA, INPUT_PULLUP);
  pinMode(SCL, OUTPUT);
  for (uint8_t i = 0; i < 9 && digitalRead(SDA) == LOW; ++i) {
    digitalWrite(SCL, LOW);
    delayMicroseconds(5);
    digitalWrite(SCL, HIGH);
    delayMicroseconds(5);
  }
  pinMode(SDA, OUTPUT);
  digitalWrite(SDA, LOW);
  delayMicroseconds(5);
  digitalWrite(SCL, HIGH);
  delayMicroseconds(5);
  digitalWrite(SDA, HIGH);  // STOP
  delayMicroseconds(5);
  pinMode(SDA, INPUT);
  pinMode(SCL, INPUT);
  beginBus();
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
  uint8_t wanted = 0, done = 0, retries = 0;
  uint32_t sum0 = 0, sum1 = 0;
  bool saturated = false;
  unsigned long started = 0, nextPoll = 0;
} reading;

const uint8_t MAX_RETRIES = 3;

uint16_t integrationMs() { return (atime + 1) * 100; }
uint16_t fullScale() { return atime == 0 ? 36863 : 65535; }

void applyLed() { analogWrite(DAC, ledPower); }

// Configure the sensor and start an integration, recovering the bus once if I2C fails.
bool startConversion() {
  for (uint8_t attempt = 0; attempt < 2; ++attempt) {
    if (tsl2591::configure(atime, again) && tsl2591::start()) {
      reading.started = millis();
      reading.nextPoll = reading.started + integrationMs();  // don't ask before it can be ready
      return true;
    }
    tsl2591::recover();
    board.debug("I2C error: bus recovered");
  }
  return false;
}

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
  if (!sensorOk) {
    tsl2591::recover();  // it may only be the bus that is stuck
    sensorOk = tsl2591::present();
  }
  if (!sensorOk) return rq.fail(LabInt::ERR_HARDWARE, "TSL2591 not found");
  reading = Reading();
  if (!startConversion()) return rq.fail(LabInt::ERR_HARDWARE, "sensor not answering");
  reading.active = true;
  reading.wanted = (uint8_t)n;
  rq.busy();
}

void cmdDiag(LabInt::Request& rq) {
  sensorOk = tsl2591::present();
  if (!sensorOk) {
    tsl2591::recover();
    sensorOk = tsl2591::present();
  }
  rq.ok().kv("sensor", sensorOk ? "ok" : "missing").kv("dac_bits", 12L)
      .kv("i2c_errors", tsl2591::errors).kv("recoveries", tsl2591::recoveries).send();
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
// A failed conversion is retried (after recovering the bus) before it becomes a FAULT.
void retryOrFault(const char* why) {
  if (reading.retries++ < MAX_RETRIES) {
    tsl2591::recover();
    board.debug("I2C error during READ: bus recovered, conversion restarted");
    if (startConversion()) return;
  }
  reading.active = false;
  tsl2591::powerOff();
  photo.fault(LabInt::ERR_HARDWARE, why);
}

void updateReading() {
  if (!reading.active || (long)(millis() - reading.nextPoll) < 0) return;
  reading.nextPoll = millis() + 5;  // then every 5 ms: a few I2C transactions per reading, not thousands
  int state = tsl2591::ready();
  if (state == 0) {
    if (millis() - reading.started > 2UL * integrationMs() + 250) retryOrFault("sensor timeout");
    return;
  }
  uint16_t c0 = 0, c1 = 0;
  if (state < 0 || !tsl2591::counts(c0, c1)) {
    retryOrFault("I2C error");
    return;
  }
  reading.sum0 += c0;
  reading.sum1 += c1;
  if (c0 >= fullScale() || c1 >= fullScale()) reading.saturated = true;
  reading.done++;
  if (reading.done < reading.wanted) {
    if (!startConversion()) retryOrFault("sensor not answering");
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
  tsl2591::beginBus();
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
