#pragma once
// Host-only Arduino shim for protocol/timing tests. Not a board/toolchain test.
#include <cstdint>
#include <string>
#define HIGH 1
#define LOW 0
#define OUTPUT 1
inline uint32_t test_millis = 0;
inline int levels[64] = {};
inline uint32_t millis() { return test_millis; }
inline void digitalWrite(uint8_t pin, int level) { levels[pin] = level; }
inline void pinMode(uint8_t, int) {}
inline void yield() {}
struct SerialStub {
    std::string input, output;
    void begin(int) {}
    int available() { return static_cast<int>(input.size()); }
    int read() { auto c = input.front(); input.erase(input.begin()); return c; }
    void print(const char* value) { output += value; }
    void print(uint32_t value) { output += std::to_string(value); }
    void println(const char* value) { output += std::string(value) + "\n"; }
    void println(uint32_t value) { output += std::to_string(value) + "\n"; }
};
inline SerialStub Serial;
