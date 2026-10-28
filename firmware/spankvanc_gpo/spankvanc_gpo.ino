// SpankVANC serial GPO bench firmware: ESP32 / ESP8266, Arduino framework.
// PULSE <sequence> <channel 1..4> <milliseconds 10..10000>\n
// Replies: ACK <sequence>, DUP <sequence>, ERR. HELLO returns protocol identity.
// GPIO is 3.3V logic: use an isolated relay/interface for a contact closure.
#include <Arduino.h>
#include <ctype.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>

#if defined(ESP8266)
const uint8_t pins[4] = {5, 4, 14, 12};
#elif defined(ESP32)
const uint8_t pins[4] = {18, 19, 21, 22}; // original ESP32; adapt for other board variants
#else
#error "Select an ESP32 or ESP8266 board"
#endif
const bool activeHigh = true;
uint32_t until[4] = {};
bool active[4] = {};
uint32_t recent[64] = {};
size_t recentIndex = 0;
char buffer[96];
size_t used = 0;
bool overflow = false;

bool number(char* token, uint32_t& value) {
  if (!token || !*token) return false;
  for (char* p = token; *p; ++p) if (!isdigit(static_cast<unsigned char>(*p))) return false;
  errno = 0;
  char* end;
  unsigned long result = strtoul(token, &end, 10);
  if (errno || *end || result > UINT32_MAX) return false;
  value = static_cast<uint32_t>(result);
  return true;
}

void command(char* line) {
  if (!strcmp(line, "HELLO")) { Serial.println("SPANKVANC 1 4"); return; }
  char* context = nullptr;
  char* verb = strtok_r(line, " ", &context);
  uint32_t sequence, channel, duration;
  if (!verb || strcmp(verb, "PULSE") ||
      !number(strtok_r(nullptr, " ", &context), sequence) || sequence == 0 ||
      !number(strtok_r(nullptr, " ", &context), channel) || channel < 1 || channel > 4 ||
      !number(strtok_r(nullptr, " ", &context), duration) || duration < 10 || duration > 10000 ||
      strtok_r(nullptr, " ", &context)) { Serial.println("ERR"); return; }
  for (uint32_t old : recent) if (old == sequence) {
    Serial.print("DUP "); Serial.println(sequence); return;
  }
  recent[recentIndex++ % 64] = sequence;
  const unsigned index = channel - 1;
  const uint32_t now = millis();
  // A distinct cue may extend an existing pulse, but never shorten it.
  if (!active[index] || static_cast<int32_t>(until[index] - now) < static_cast<int32_t>(duration))
    until[index] = now + duration;
  active[index] = true;
  digitalWrite(pins[index], activeHigh ? HIGH : LOW);
  Serial.print("ACK "); Serial.println(sequence);
}

void setup() {
  for (uint8_t pin : pins) {
    digitalWrite(pin, activeHigh ? LOW : HIGH);
    pinMode(pin, OUTPUT);
  }
  Serial.begin(115200);
}

void loop() {
  uint32_t now = millis();
  for (unsigned i = 0; i < 4; ++i) {
    if (active[i] && static_cast<int32_t>(now - until[i]) >= 0) {
      digitalWrite(pins[i], activeHigh ? LOW : HIGH);
      active[i] = false;
    }
  }
  // Bound serial work so traffic cannot starve pulse expiry.
  for (unsigned count = 0; count < 64 && Serial.available(); ++count) {
    const char c = static_cast<char>(Serial.read());
    if (c == '\r') continue;
    if (c == '\n') {
      buffer[used] = 0;
      if (overflow) Serial.println("ERR"); else command(buffer);
      used = 0; overflow = false;
    } else if (used + 1 < sizeof(buffer) && !overflow && c >= 32 && c <= 126) {
      buffer[used++] = c;
    } else { overflow = true; }
  }
  yield();
}
