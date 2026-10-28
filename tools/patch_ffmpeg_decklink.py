"""Add ST 334-1 legacy 608 packet capture to the pinned FFmpeg DeckLink input.

Existing FFmpeg handles CDP (61/01) via VANC lines. This fallback uses the SDK
packet interface for 61/02 only, and never replaces a CDP-derived A/53 block.
"""
from pathlib import Path
import sys

source = Path(sys.argv[1]) / 'libavdevice/decklink_dec.cpp'
text = source.read_text()
marker = '        pkt.buf = av_buffer_create(pkt.data, pkt.size, decklink_object_free, videoFrame, 0);'
patch = '''        // SpankVANC: legacy ST 334-1 608 ANC, Annex B field polarity.
        // Prefer a CDP already decoded above when both packet types exist.
        if (!no_video && !av_packet_get_side_data(&pkt, AV_PKT_DATA_A53_CC, NULL)) {
            IDeckLinkVideoFrameAncillaryPackets *packets = NULL;
            if (videoFrame->QueryInterface(IID_IDeckLinkVideoFrameAncillaryPackets,
                                          (void **)&packets) == S_OK) {
                IDeckLinkAncillaryPacketIterator *iterator = NULL;
                std::vector<uint8_t> cc;
                if (packets->GetPacketIterator(&iterator) == S_OK) {
                    IDeckLinkAncillaryPacket *packet = NULL;
                    while (iterator->Next(&packet) == S_OK) {
                        const void *bytes = NULL;
                        uint32_t size = 0;
                        if (packet->GetDID() == 0x61 && packet->GetSDID() == 0x02 &&
                            packet->GetBytes(bmdAncillaryPacketFormatUInt8, &bytes, &size) == S_OK &&
                            size == 3 && cc.size() < 90) {
                            const uint8_t *p = (const uint8_t *)bytes;
                            cc.push_back((p[0] & 0x80) ? 0xfc : 0xfd);
                            cc.push_back(p[1]);
                            cc.push_back(p[2]);
                        }
                        packet->Release();
                    }
                    iterator->Release();
                }
                packets->Release();
                if (!cc.empty()) {
                    uint8_t *data = av_packet_new_side_data(&pkt, AV_PKT_DATA_A53_CC, cc.size());
                    if (data)
                        memcpy(data, cc.data(), cc.size());
                }
            }
        }

'''
if '// SpankVANC: legacy ST 334-1' not in text:
    if text.count(marker) != 1:
        raise SystemExit('Unexpected FFmpeg source: capture insertion point differs')
    source.write_text(text.replace(marker, patch + marker))
print('DeckLink 608 packet fallback installed')
