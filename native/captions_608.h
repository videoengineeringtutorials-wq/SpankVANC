#pragma once

#include <algorithm>
#include <cstdint>
#include <deque>
#include <string>
#include <vector>

// CC1 on Field 1, with a two-row window anchored at rows 14 and 15.
enum class CaptionMode { RollUp, PopOn };

struct CCEncoder {
    CaptionMode mode = CaptionMode::RollUp;
    std::deque<std::pair<uint8_t, uint8_t>> pending;
    bool initialized = false;
    std::string last_message;
    std::string last_line;
};

static inline uint8_t parity(uint8_t c)
{
    c &= 0x7F;
    return (__builtin_popcount(c) & 1) ? c : (c | 0x80);
}

// Wrap printable ASCII at word boundaries; explicit newlines are respected.
// At most two lines of 32 characters are displayed per UDP message.
static inline std::vector<std::string> caption_lines(const std::string& text)
{
    std::string input;
    for (unsigned char c : text) {
        if (c == '\r') continue;
        if (c == '\n') input += '\n';
        else if (c == '\t') input += ' ';
        else if (c >= 0x20 && c <= 0x7E) input += static_cast<char>(c);
    }
    std::vector<std::string> lines;
    while (!input.empty() && lines.size() < 2) {
        size_t leading = input.find_first_not_of(" \n");
        if (leading == std::string::npos) break;
        input.erase(0, leading);
        size_t newline = input.find('\n');
        size_t end = std::min<size_t>(32, std::min(input.size(), newline));
        size_t consumed = end;
        if (end == 32 && input.size() > 32 && input[32] != ' ' && input[32] != '\n') {
            size_t space = input.rfind(' ', 32);
            if (space != std::string::npos && space > 0) end = consumed = space;
        }
        std::string line = input.substr(0, end);
        size_t last = line.find_last_not_of(' ');
        if (last != std::string::npos) lines.push_back(line.substr(0, last + 1));
        input.erase(0, consumed);
    }
    return lines;
}

// Duplicate control codes for reliable 608 reception. A decoder executes them
// once; repeating text pairs would instead print duplicate characters.
static inline void cc_control(CCEncoder& enc, uint8_t a, uint8_t b)
{
    enc.pending.emplace_back(a, b);
    enc.pending.emplace_back(a, b);
}

static inline void cc_text(CCEncoder& enc, const std::string& line)
{
    for (size_t i = 0; i < line.size(); i += 2)
        enc.pending.emplace_back(line[i], i + 1 < line.size() ? line[i + 1] : ' ');
}

static inline void set_caption(CCEncoder& enc, const std::string& text)
{
    auto lines = caption_lines(text);
    if (lines.empty()) {
        // A blank UDP update explicitly clears both caption memories.
        cc_control(enc, 0x14, 0x2C);
        cc_control(enc, 0x14, 0x2E);
        enc.initialized = false;
        enc.last_message.clear();
        enc.last_line.clear();
        return;
    }
    std::string message = lines[0] + (lines.size() == 2 ? "\n" + lines[1] : "");
    if (message == enc.last_message) return;
    enc.last_message = message;

    if (enc.mode == CaptionMode::RollUp) {
        // Reassert the two-row mode on every update, including receivers that
        // joined after the initial caption. RU2 retains an existing RU2 window.
        cc_control(enc, 0x14, 0x25);
        if (!enc.initialized) {
            cc_control(enc, 0x14, 0x2C); // erase displayed memory
            cc_control(enc, 0x14, 0x2E); // erase hidden memory
        }
        for (const auto& line : lines) {
            cc_control(enc, 0x14, 0x70); // PAC: row 15, explicit indent 0
            if (enc.initialized) cc_control(enc, 0x14, 0x2D); // roll previous line up
            cc_control(enc, 0x14, 0x70); // bottom row, reset column
            cc_control(enc, 0x14, 0x24); // delete entire destination row
            cc_text(enc, line);
            cc_control(enc, 0x14, 0x24); // delete any residual suffix after text
            enc.initialized = true;
        }
    } else {
        // Single-line messages retain the previous line above the new one;
        // an explicit/wrapped two-line message replaces the whole caption.
        if (lines.size() == 1 && !enc.last_line.empty())
            lines.insert(lines.begin(), enc.last_line);
        cc_control(enc, 0x14, 0x20); // RCL: load hidden memory
        cc_control(enc, 0x14, 0x2E); // clear hidden memory, avoid stale text
        if (lines.size() == 2) {
            cc_control(enc, 0x14, 0x50); // PAC: row 14, explicit indent 0
            cc_control(enc, 0x14, 0x24);
            cc_text(enc, lines[0]);
            cc_control(enc, 0x14, 0x24);
        }
        cc_control(enc, 0x14, 0x70); // PAC: row 15, explicit indent 0
        cc_control(enc, 0x14, 0x24);
        cc_text(enc, lines.back());
        cc_control(enc, 0x14, 0x24);
        cc_control(enc, 0x14, 0x2F); // EOC: swap completed caption onto screen
        cc_control(enc, 0x14, 0x2E); // clear the old screen now in hidden memory
        enc.initialized = true;
    }
    enc.last_line = lines.back();
}

static inline void build_cc(std::vector<uint8_t>& out, CCEncoder& enc)
{
    uint8_t a = 0, b = 0;
    if (!enc.pending.empty()) {
        a = enc.pending.front().first;
        b = enc.pending.front().second;
        enc.pending.pop_front();
    }
    // 1080i has one pair per field per frame. Carry CC1 only on Field 1;
    // Field 2 is invalid padding, not a duplicate CC3 caption service.
    out = {0xFC, parity(a), parity(b), 0xF9, 0x80, 0x80};
}
