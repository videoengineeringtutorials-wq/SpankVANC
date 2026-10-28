#include "anc_policy.hpp"
#include <cassert>
#include <iostream>
using namespace spankvanc;
int main() {
    const std::vector<AncPacket> source = {
        {0x61, 0x01, 9, 1, 90000, {0x96, 0x69, 0x11}},
        {0x61, 0x02, 21, 1, 90000, {0x94, 0x20}},
        {0x41, 0x07, 13, 1, 90000, {0x08, 0xff, 0xff}},
        {0x41, 0x05, 11, 1, 90000, {0x01, 0x02}}};
    auto no_cc = filter(source, Policy::Strip, Policy::Pass);
    assert(no_cc.size() == 2 && no_cc[0].sdid == 0x07 && no_cc[1].sdid == 0x05);
    assert(no_cc[0].payload == source[2].payload && no_cc[0].line == 13 && no_cc[0].pts90k == 90000);
    auto no_scte = filter(source, Policy::Pass, Policy::Strip);
    assert(no_scte.size() == 3 && no_scte[0].did == 0x61);
    auto replace = filter(source, Policy::Replace, Policy::Replace);
    assert(replace.size() == 1 && replace[0].sdid == 0x05);
    assert(filter(source, Policy::Pass, Policy::Pass, true).empty());
    assert(source.size() == 4); // each output owns its own independently filtered packets
    std::cout << "ANC classification, independent stripping and byte preservation passed\n";
}
