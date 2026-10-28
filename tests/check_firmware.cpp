#include "../firmware/spankvanc_gpo/spankvanc_gpo.ino"
#include <cassert>
#include <iostream>
static std::string send(const std::string& input) {
    Serial.input = input;
    Serial.output.clear();
    while (Serial.available()) loop();
    return Serial.output;
}
int main() {
    setup();
    for (auto pin : pins) assert(levels[pin] == LOW);
    assert(send("HELLO\n") == "SPANKVANC 1 4\n");
    assert(send("PULSE 42 2 250\n") == "ACK 42\n");
    assert(levels[pins[1]] == HIGH);
    test_millis = 100;
    assert(send("PULSE 42 2 250\n") == "DUP 42\n");
    assert(until[1] == 250); // retry does not repeat/extend the pulse
    assert(send("PULSE 43 2 50\n") == "ACK 43\n");
    assert(until[1] == 250); // shorter overlapping event does not shorten it
    test_millis = 251; loop();
    assert(levels[pins[1]] == LOW);
    for (auto invalid : {"PULSE 0 1 250\n", "PULSE 44 0 250\n", "PULSE 44 1 10001\n",
                         "PULSE -1 1 250\n", "PULSE 4294967296 1 250\n", "PULSE 44 1 250 extra\n"})
        assert(send(invalid) == "ERR\n");
    assert(send(std::string(150, 'x') + "\nHELLO\n") == "ERR\nSPANKVANC 1 4\n");
    // Firmware expiry arithmetic must survive millis() wrapping to zero.
    test_millis = 0xfffffffe;
    assert(send("PULSE 45 1 10\n") == "ACK 45\n");
    test_millis = 9; loop();
    assert(levels[pins[0]] == LOW);
    std::cout << "Firmware host simulation passed: validation, duplicates, pulses, overflow and clock wrap\n";
}
