#include "platform.h"

#include <EEPROM.h>
#include <string.h>

#if defined(ARDUINO_ARCH_RENESAS)
#include "bsp_api.h"
#endif

// EEPROM layout (emulated in flash on Renesas):
//   0..3   magic "LI1\0"
//   4..9   random serial (boards without a hardware ID)
//   16..40 name (24 characters + terminator)
//   64..95 sketch settings, one byte per slot
namespace {
const int MAGIC = 0, RANDOM_SERIAL = 4, NAME = 16, SETTINGS = 64, SETTINGS_COUNT = 32;
const char MAGIC_TEXT[4] = {'L', 'I', '1', 0};

void ensureFormatted() {
  bool ok = true;
  for (int i = 0; i < 4; ++i) ok = ok && EEPROM.read(MAGIC + i) == (uint8_t)MAGIC_TEXT[i];
  if (ok) return;
  randomSeed(micros() ^ (unsigned long)analogRead(A1));
  for (int i = 0; i < 6; ++i) EEPROM.update(RANDOM_SERIAL + i, (uint8_t)random(256));
  EEPROM.update(NAME, 0);
  for (int i = 0; i < SETTINGS_COUNT; ++i) EEPROM.update(SETTINGS + i, 0xFF);
  for (int i = 0; i < 4; ++i) EEPROM.update(MAGIC + i, (uint8_t)MAGIC_TEXT[i]);
}

void hex(const uint8_t* bytes, size_t n, char* out, size_t size) {
  static const char digits[] = "0123456789ABCDEF";
  size_t k = 0;
  for (size_t i = 0; i < n && k + 2 < size; ++i) {
    out[k++] = digits[bytes[i] >> 4];
    out[k++] = digits[bytes[i] & 0xF];
  }
  out[k] = 0;
}
}  // namespace

namespace labint_platform {

const char* boardType() {
#if defined(ARDUINO_MINIMA)
  return "uno-r4-minima";
#elif defined(ARDUINO_UNOWIFIR4)
  return "uno-r4-wifi";
#elif defined(ARDUINO_AVR_UNO)
  return "uno";
#elif defined(ARDUINO_AVR_MEGA2560)
  return "mega";
#elif defined(ARDUINO_AVR_NANO)
  return "nano";
#elif defined(ARDUINO_ARCH_ESP32)
  return "esp32";
#elif defined(ARDUINO_TEENSY41)
  return "teensy41";
#elif defined(ARDUINO_ARCH_STM32)
  return "stm32";
#else
  return "arduino";
#endif
}

void serialNumber(char* out, size_t size) {
  uint8_t id[6];
#if defined(ARDUINO_ARCH_RENESAS)
  // 128-bit factory ID of the RA microcontroller, folded to 48 bits.
  const bsp_unique_id_t* uid = R_BSP_UniqueIdGet();
  const uint8_t* raw = (const uint8_t*)uid->unique_id_bytes;
  memset(id, 0, sizeof(id));
  for (int i = 0; i < 16; ++i) id[i % 6] ^= raw[i];
#else
  ensureFormatted();
  for (int i = 0; i < 6; ++i) id[i] = EEPROM.read(RANDOM_SERIAL + i);
#endif
  hex(id, sizeof(id), out, size);
}

void loadName(char* out, size_t size) {
  ensureFormatted();
  size_t i = 0;
  for (; i + 1 < size && i < 24; ++i) {
    char c = (char)EEPROM.read(NAME + i);
    if (!c || (uint8_t)c == 0xFF) break;
    out[i] = c;
  }
  out[i] = 0;
}

void saveName(const char* name) {
  ensureFormatted();
  size_t n = strlen(name);
  if (n > 24) n = 24;
  for (size_t i = 0; i < n; ++i) EEPROM.update(NAME + i, (uint8_t)name[i]);
  EEPROM.update(NAME + n, 0);
}

uint8_t loadSetting(uint8_t slot, uint8_t def) {
  if (slot >= SETTINGS_COUNT) return def;
  ensureFormatted();
  uint8_t v = EEPROM.read(SETTINGS + slot);
  return v == 0xFF ? def : v;
}

void saveSetting(uint8_t slot, uint8_t value) {
  if (slot >= SETTINGS_COUNT) return;
  ensureFormatted();
  EEPROM.update(SETTINGS + slot, value);
}

}  // namespace labint_platform
