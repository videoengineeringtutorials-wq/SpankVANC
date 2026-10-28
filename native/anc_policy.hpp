#pragma once
#include <cstdint>
#include <vector>

namespace spankvanc {
// Payload bytes are owned and retain their frame/line association. Actual SDK
// capture/playout and ST 2010 fragmentation are separate adapter responsibilities.
struct AncPacket {
    uint8_t did, sdid;
    uint32_t line;
    uint8_t stream;
    int64_t pts90k;
    std::vector<uint8_t> payload;
};
enum class Policy { Pass, Strip, Replace };
enum class AncKind { Captions, Scte104, Other };
inline AncKind classify(const AncPacket& p) {
    if (p.did == 0x61 && (p.sdid == 0x01 || p.sdid == 0x02)) return AncKind::Captions;
    if (p.did == 0x41 && p.sdid == 0x07) return AncKind::Scte104;
    return AncKind::Other;
}
inline std::vector<AncPacket> filter(const std::vector<AncPacket>& packets,
        Policy captions, Policy scte, bool strip_all_vanc = false) {
    std::vector<AncPacket> result;
    if (strip_all_vanc) return result;
    for (const auto& p : packets) {
        const auto kind = classify(p);
        if (kind == AncKind::Captions && captions != Policy::Pass) continue;
        if (kind == AncKind::Scte104 && scte != Policy::Pass) continue;
        result.push_back(p);
    }
    return result;
}
} // namespace spankvanc
