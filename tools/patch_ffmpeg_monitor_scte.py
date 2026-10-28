"""Extend the pinned private FFmpeg with source telemetry and SCTE-35 sections."""
from pathlib import Path
import sys

root=Path(sys.argv[1]);project=Path(__file__).resolve().parent.parent

def edit(name,marker,old,new):
    p=root/name;s=p.read_text()
    if marker in s:return
    if s.count(old)!=1 and marker!='// SpankVANC SCTE stream type':raise SystemExit(f'Unexpected FFmpeg insertion point: {name}: {old[:70]}')
    p.write_text(s.replace(old,new,1))


def generated(name, start, end, content):
    """Refresh only a block owned by this patch, including already patched builds."""
    p=root/name;s=p.read_text()
    if start not in s:
        if s.count(end)!=1:raise SystemExit(f'Unexpected generated block boundary: {name}')
        new=s.replace(end,content+end,1)
    else:
        begin=s.index(start);finish=s.index(end,begin)
        new=s[:begin]+content+s[finish:]
    if new!=s:p.write_text(new)

header=root/'libavdevice/spankvanc_scte104.hpp'
content=(project/'native/scte104.hpp').read_text()
if not header.exists() or header.read_text()!=content:header.write_text(content)
edit('libavdevice/decklink_common_c.h','int spankvanc_anc;', '    int enable_klv;', '    int enable_klv;\n    int spankvanc_anc;\n    int spankvanc_scte35;')
edit('libavdevice/decklink_common_c.h','int spankvanc_scte_strict;', '    int spankvanc_scte35;', '    int spankvanc_scte35;\n    int spankvanc_scte_strict;')
edit('libavdevice/decklink_common.h','class SpankPlaceholder;', 'class decklink_output_callback;', 'class SpankPlaceholder; // SpankVANC marker\nnamespace spankvanc { class Scte104Decoder; }\nclass decklink_output_callback;')
edit('libavdevice/decklink_common.h','spank_scte_st;', '    AVStream *klv_st;', '    AVStream *klv_st;\n    AVStream *spank_scte_st;\n    spankvanc::Scte104Decoder *spank_scte;\n    int64_t spank_next_null;')
edit('libavdevice/decklink_dec_c.c','"spankvanc_anc"', '    { NULL },', '''    { "spankvanc_anc", "SpankVANC source monitor telemetry v1", OFFSET(spankvanc_anc), AV_OPT_TYPE_BOOL, { .i64 = 0 }, 0, 1, DEC },
    { "spankvanc_scte35", "SpankVANC ST2010 program-splice conversion v1", OFFSET(spankvanc_scte35), AV_OPT_TYPE_BOOL, { .i64 = 0 }, 0, 1, DEC },
    { NULL },''')
edit('libavdevice/decklink_dec_c.c','"spankvanc_scte_strict"','    { NULL },', '    { "spankvanc_scte_strict", "Stop A/V on rejected SCTE message (0 continues A/V and reports discarded cues)", OFFSET(spankvanc_scte_strict), AV_OPT_TYPE_BOOL, { .i64 = 0 }, 0, 1, DEC },\n    { NULL },')
edit('libavdevice/decklink_dec.cpp','"spankvanc_scte104.hpp"', '#include <atomic>', '#include "spankvanc_scte104.hpp"\n#include <sstream>\n#include <iomanip>\n#include <atomic>')
edit('libavdevice/decklink_dec.cpp','ctx->spank_scte_st = st;', '    ctx->video_st=st;', '''    ctx->video_st=st;
    if (cctx->spankvanc_scte35) {
        st = avformat_new_stream(avctx, NULL);
        if (!st) { ret = AVERROR(ENOMEM); goto error; }
        st->codecpar->codec_type = AVMEDIA_TYPE_DATA;
        st->codecpar->codec_id = AV_CODEC_ID_SCTE_35;
        avpriv_set_pts_info(st, 64, 1, 1000000);
        ctx->spank_scte_st = st;
        ctx->spank_scte = new spankvanc::Scte104Decoder;
    }''')
edit('libavdevice/decklink_dec.cpp','delete ctx->spank_scte;', '    ff_decklink_packet_queue_end(&ctx->queue);', '    ff_decklink_packet_queue_end(&ctx->queue);\n    delete ctx->spank_scte;\n    ctx->spank_scte = nullptr;')
# On read-header failure, cleanup first stops callbacks before destroying state.
edit('libavdevice/decklink_dec.cpp','// SpankVANC header cleanup', 'error:\n    ff_decklink_cleanup(avctx);', 'error:\n    ff_decklink_cleanup(avctx);\n    delete ctx->spank_scte; // SpankVANC header cleanup\n    ctx->spank_scte = nullptr;')
edit('libavdevice/decklink_dec.cpp','spank_scte->failed.load()', '    ff_decklink_packet_queue_get(&ctx->queue, pkt, 1);', '    if (ctx->spank_scte && ctx->spank_scte->failed.load())\n        return AVERROR_INVALIDDATA;\n    ff_decklink_packet_queue_get(&ctx->queue, pkt, 1);')
block='''        // SpankVANC source monitor and SCTE capture v1. Same owner as A/V.
        if (cctx->spankvanc_anc || ctx->spank_scte) {
            int64_t source_pts = av_rescale_q(pkt.pts, ctx->video_st->time_base, AVRational{1,90000});
            std::vector<spankvanc::ScteResult> sections;
            std::ostringstream telemetry;
            auto json_quote = [](const std::string &value) {
                std::string out(1, char(34));
                for (unsigned char ch : value) {
                    if (ch == 92 || ch == 34) out += char(92);
                    out += ch >= 32 ? char(ch) : ' ';
                }
                return out + char(34);
            };
            telemetry << "SPANKVANC {\\"pts90k\\":" << source_pts
                      << ",\\"signal\\":" << (no_video ? "false" : "true") << ",\\"cc\\":\\"";
            size_t cc_size = 0;
            const uint8_t *cc = av_packet_get_side_data(&pkt, AV_PKT_DATA_A53_CC, &cc_size);
            for (size_t k = 0; k < cc_size; ++k)
                telemetry << std::hex << std::setw(2) << std::setfill('0') << int(cc[k]);
            telemetry << "\\",\\"scte104\\":[";
            bool comma = false;
            IDeckLinkVideoFrameAncillaryPackets *packets = NULL;
            if (!no_video && videoFrame->QueryInterface(IID_IDeckLinkVideoFrameAncillaryPackets, (void **)&packets) == S_OK) {
                IDeckLinkAncillaryPacketIterator *iterator = NULL;
                if (packets->GetPacketIterator(&iterator) == S_OK) {
                    IDeckLinkAncillaryPacket *packet = NULL;
                    while (iterator->Next(&packet) == S_OK) {
                        const void *bytes = NULL;
                        uint32_t size = 0;
                        if (packet->GetDID() == 0x41 && packet->GetSDID() == 0x07 &&
                            packet->GetBytes(bmdAncillaryPacketFormatUInt8, &bytes, &size) == S_OK && size <= 255) {
                            const uint8_t *p = (const uint8_t *)bytes;
                            if (comma) telemetry << ',';
                            comma = true; telemetry << '\\"';
                            for (uint32_t k = 0; k < size; ++k)
                                telemetry << std::hex << std::setw(2) << std::setfill('0') << int(p[k]);
                            telemetry << '\\"';
                            if (ctx->spank_scte) {
                                try {
                                    uint64_t before = ctx->spank_scte->rejected;
                                    auto converted = ctx->spank_scte->consume(p, size, source_pts, packet->GetDataStreamIndex(), cctx->spankvanc_scte_strict);
                                    if (ctx->spank_scte->rejected != before)
                                        av_log(avctx, cctx->spankvanc_scte_strict ? AV_LOG_ERROR : AV_LOG_WARNING,
                                            "SCTE-104 cue rejected (%s): %s; source_pts90k=%lld; payload=%s\\n",
                                            cctx->spankvanc_scte_strict ? "route stopping" : "A/V continuing",
                                            ctx->spank_scte->last_error.c_str(), (long long)source_pts,
                                            ctx->spank_scte->last_payload_hex.c_str());
                                    sections.insert(sections.end(), converted.begin(), converted.end());
                                } catch (const std::exception &e) {
                                    av_log(avctx, AV_LOG_ERROR, "SCTE-104 conversion rejected: %s\\n", e.what());
                                    ctx->spank_scte->failed.store(true);
                                }
                            }
                        }
                        packet->Release();
                    }
                    iterator->Release();
                }
                packets->Release();
            }
            telemetry << "],\\"converted\\":" << std::dec << sections.size()
                      << ",\\"conversion_error\\":" << ((ctx->spank_scte && ctx->spank_scte->failed.load()) ? "true" : "false") << "}";
            if (ctx->spank_scte) {
                std::string text = telemetry.str();
                text.pop_back();telemetry.str("");telemetry.clear();
                telemetry << text << ",\\"rejected_total\\":" << ctx->spank_scte->rejected
                    << ",\\"last_rejection\\":" << json_quote(ctx->spank_scte->last_error)
                    << ",\\"last_rejected_hex\\":" << json_quote(ctx->spank_scte->last_payload_hex)
                    << ",\\"last_rejected_pts90k\\":" << ctx->spank_scte->last_rejected_pts << "}";
            }
            if (cctx->spankvanc_anc)
                av_log(avctx, AV_LOG_INFO, "%s\\n", telemetry.str().c_str());
            if (ctx->spank_scte_st && !ctx->spank_scte->failed.load()) {
                if (source_pts >= ctx->spank_next_null) {
                    sections.push_back({spankvanc::section35(0, {}),0,0,0,true});
                    ctx->spank_next_null = source_pts + 90000;
                }
                for (const auto &section : sections) {
                    AVPacket cue = {0};
                    if (av_new_packet(&cue, section.section.size()) < 0) { ctx->spank_scte->failed.store(true); break; }
                    memcpy(cue.data, section.section.data(), section.section.size());
                    cue.pts = cue.dts = pkt.pts;
                    cue.stream_index = ctx->spank_scte_st->index;
                    if (section.internal_heartbeat)
                        cue.flags |= AV_PKT_FLAG_DISPOSABLE;
                    if (ff_decklink_packet_queue_put(&ctx->queue, &cue) < 0)
                        ctx->spank_scte->failed.store(true);
                }
            }
        }

'''
generated('libavdevice/decklink_dec.cpp','        // SpankVANC source monitor and SCTE capture v1.', '        pkt.buf = av_buffer_create(pkt.data, pkt.size, decklink_object_free, videoFrame, 0);', block)
# SCTE sections are PSI-style sections, never PES private-data payloads.
edit('libavformat/mpegtsenc.c','// SpankVANC SCTE stream type', '    switch (st->codecpar->codec_id) {', '    switch (st->codecpar->codec_id) {\n    case AV_CODEC_ID_SCTE_35: // SpankVANC SCTE stream type\n        stream_type = 0x86;\n        break;')
edit('libavformat/mpegtsenc.c','// SpankVANC program CUEI', '    /* put program info here */', '''    /* put program info here */
    // SpankVANC program CUEI registration, SCTE 35 signaling.
    for (unsigned j = 0; j < s->nb_streams; ++j) {
        if (s->streams[j]->codecpar->codec_id == AV_CODEC_ID_SCTE_35) {
            put_registration_descriptor(&q, MKTAG('C','U','E','I'));
            break;
        }
    }''')
edit('libavformat/mpegtsenc.c','// SpankVANC cue_identifier', '        case AVMEDIA_TYPE_DATA:\n            if (codec_id == AV_CODEC_ID_SMPTE_KLV)', '''        case AVMEDIA_TYPE_DATA:
            if (codec_id == AV_CODEC_ID_SCTE_35) {
                *q++ = 0x8a; *q++ = 1; *q++ = 1; // SpankVANC cue_identifier
            } else if (codec_id == AV_CODEC_ID_SMPTE_KLV)''')
mux='''    // SpankVANC: write complete SCTE-35 sections and translate to mux clock.
    if (st->codecpar->codec_id == AV_CODEC_ID_SCTE_35) {
        uint8_t section[4096];
        MpegTSSection writer = {0};
        uint64_t adjustment;
        if (size < 20 || size > 4096 || buf[0] != 0xfc ||
            (3 + (AV_RB16(buf + 1) & 0x0fff)) != size || (buf[4] & 0xfe))
            return AVERROR_INVALIDDATA;
        // Internal cadence packets prime probing/interleaving only. Source
        // splice_null requests do not carry DISPOSABLE and are still emitted.
        if (buf[13] == 0 && (pkt->flags & AV_PKT_FLAG_DISPOSABLE))
            return 0;
        memcpy(section, buf, size);
        adjustment = (((uint64_t)(section[4] & 1)) << 32) | AV_RB32(section + 5);
        if (ts->copyts < 1) adjustment += delay;
        adjustment &= (((uint64_t)1 << 33) - 1);
        section[4] = adjustment >> 32;
        AV_WB32(section + 5, adjustment);
        retransmit_si_info(s, 0, 0, 0, dts * (PCR_TIME_BASE / 90000));
        writer.pid = ts_st->pid;
        writer.cc = ts_st->cc;
        writer.discontinuity = ts_st->discontinuity;
        writer.write_packet = section_write_packet;
        writer.opaque = s;
        mpegts_write_section(&writer, section, size);
        ts_st->cc = writer.cc;
        ts_st->discontinuity = 0;
        return 0;
    }

'''
generated('libavformat/mpegtsenc.c','    // SpankVANC: write complete SCTE-35', '    if (st->codecpar->codec_id == AV_CODEC_ID_H264) {', mux)
print('Source monitor and SCTE-35 capture/mux patches installed')
