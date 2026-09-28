// What differs between microcontrollers: board type, unique serial number, persistent storage.
#pragma once

#include <Arduino.h>

namespace labint_platform {
const char* boardType();
void serialNumber(char* out, size_t size);  // 12 hex digits, stable for this board
void loadName(char* out, size_t size);      // "" if never set
void saveName(const char* name);
uint8_t loadSetting(uint8_t slot, uint8_t def);
void saveSetting(uint8_t slot, uint8_t value);
}  // namespace labint_platform
