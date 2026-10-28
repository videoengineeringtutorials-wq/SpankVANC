"""Private frame-attached SCTE-104 pass and SCTE-35 -> 104 SDI output."""
from pathlib import Path
import sys
root=Path(sys.argv[1]);project=Path(__file__).resolve().parent.parent

def edit(name,marker,old,new):
 p=root/name;s=p.read_text()
 if marker in s:return
 if s.count(old)!=1:raise SystemExit('Unexpected SCTE output insertion: '+name+': '+old[:60])
 p.write_text(s.replace(old,new,1))

for name in ('scte104.hpp','scte35_to104.hpp','scte_vanc.hpp'):
 (root/'libavdevice'/('spankvanc_'+name)).write_text((project/'native'/name).read_text().replace('"scte104.hpp"','"spankvanc_scte104.hpp"').replace('"scte35_to104.hpp"','"spankvanc_scte35_to104.hpp"'))
edit('libavcodec/packet.h','AV_PKT_DATA_SPANKVANC_SCTE104,','    AV_PKT_DATA_NB','    AV_PKT_DATA_SPANKVANC_SCTE104,\n    AV_PKT_DATA_NB')
edit('libavutil/frame.h','AV_FRAME_DATA_SPANKVANC_SCTE104,','    AV_FRAME_DATA_VIDEO_HINT,','    AV_FRAME_DATA_VIDEO_HINT,\n    AV_FRAME_DATA_SPANKVANC_SCTE104,')
edit('libavcodec/avpacket.c','case AV_PKT_DATA_SPANKVANC_SCTE104:', '    case AV_PKT_DATA_A53_CC:', '    case AV_PKT_DATA_SPANKVANC_SCTE104: return "SpankVANC SCTE-104 ANC";\n    case AV_PKT_DATA_A53_CC:')
edit('libavutil/frame.c','case AV_FRAME_DATA_SPANKVANC_SCTE104:', '    case AV_FRAME_DATA_A53_CC:', '    case AV_FRAME_DATA_SPANKVANC_SCTE104: return "SpankVANC SCTE-104 ANC";\n    case AV_FRAME_DATA_A53_CC:')
edit('libavcodec/decode.c','{ AV_PKT_DATA_SPANKVANC_SCTE104,', '        { AV_PKT_DATA_A53_CC,', '        { AV_PKT_DATA_SPANKVANC_SCTE104, AV_FRAME_DATA_SPANKVANC_SCTE104 },\n        { AV_PKT_DATA_A53_CC,')
edit('libavcodec/v210enc.c','/* SpankVANC SCTE-104 V210 */','    *got_packet = 1;', '''    /* SpankVANC SCTE-104 V210 */
    const AVFrameSideData *scte104 = av_frame_get_side_data(pic, AV_FRAME_DATA_SPANKVANC_SCTE104);
    if (scte104) {
        uint8_t *data = av_packet_new_side_data(pkt, AV_PKT_DATA_SPANKVANC_SCTE104, scte104->size);
        if (!data) return AVERROR(ENOMEM);
        memcpy(data, scte104->data, scte104->size);
    }
    *got_packet = 1;''')
edit('libavdevice/decklink_common_c.h','int spankvanc_scte104;', '    int spankvanc_caption_output;', '    int spankvanc_caption_output;\n    int spankvanc_scte104;\n    int spankvanc_scte_output;\n    int spankvanc_scte_output_strict;')
edit('libavdevice/decklink_common.h','class Scte35To104;', 'class Scte104Decoder;', 'class Scte104Decoder; class Scte35To104;')
edit('libavdevice/decklink_common.h','spank_to104;', '    int64_t spank_next_null;', '    int64_t spank_next_null;\n    int spank_scte104_failed;\n    spankvanc::Scte35To104 *spank_to104;')
edit('libavdevice/decklink_dec_c.c','"spankvanc_scte104"', '    { NULL },', '    { "spankvanc_scte104", "Preserve primary-stream SCTE-104 ANC on source frames", OFFSET(spankvanc_scte104), AV_OPT_TYPE_BOOL, { .i64 = 0 }, 0, 1, DEC },\n    { NULL },')
edit('libavdevice/decklink_dec.cpp','"spankvanc_scte35_to104.hpp"', '#include "spankvanc_scte104.hpp"', '#include "spankvanc_scte104.hpp"\n#include "spankvanc_scte35_to104.hpp"')
capture='''        // SpankVANC opaque SCTE-104 source-frame carriage.
        if (cctx->spankvanc_scte104 && !no_video) {
            try {
                std::vector<spankvanc::Anc104> saved;
                IDeckLinkVideoFrameAncillaryPackets *packets = NULL;
                if (videoFrame->QueryInterface(IID_IDeckLinkVideoFrameAncillaryPackets, (void **)&packets) != S_OK)
                    throw std::runtime_error("SCTE-104 ANC capture interface unavailable");
                IDeckLinkAncillaryPacketIterator *iterator = NULL;
                HRESULT status = packets->GetPacketIterator(&iterator);
                packets->Release();
                if (status != S_OK) throw std::runtime_error("Cannot enumerate SCTE-104 ANC");
                IDeckLinkAncillaryPacket *packet = NULL;
                bool invalid = false;
                while (iterator->Next(&packet) == S_OK) {
                    if (packet->GetDID() == 0x41 && packet->GetSDID() == 0x07) {
                        const void *bytes = NULL; uint32_t size = 0;
                        if (packet->GetBytes(bmdAncillaryPacketFormatUInt8, &bytes, &size) != S_OK ||
                            !bytes || !size || size > 255 || saved.size() >= 128 ||
                            packet->GetDataStreamIndex() != 0 || !packet->GetLineNumber() || packet->GetLineNumber() > 2047) invalid = true;
                        else saved.push_back({uint16_t(packet->GetLineNumber()), 0,
                            spankvanc::Bytes((const uint8_t*)bytes, (const uint8_t*)bytes + size)});
                    }
                    packet->Release();
                }
                iterator->Release();
                if (invalid) throw std::runtime_error("Unsupported SCTE-104 ANC stream/line/size/count");
                if (!saved.empty()) {
                    auto data = spankvanc::pack104(saved);
                    uint8_t *side = av_packet_new_side_data(&pkt, AV_PKT_DATA_SPANKVANC_SCTE104, data.size());
                    if (!side) throw std::bad_alloc();
                    memcpy(side, data.data(), data.size());
                }
            } catch (const std::exception& e) {
                av_log(avctx, AV_LOG_ERROR, "SCTE-104 passthrough failed: %s\\n", e.what());
                __atomic_store_n(&ctx->spank_scte104_failed, 1, __ATOMIC_RELEASE);
            }
        }

'''
edit('libavdevice/decklink_dec.cpp','// SpankVANC opaque SCTE-104 source-frame carriage.', '        pkt.buf = av_buffer_create(pkt.data, pkt.size, decklink_object_free, videoFrame, 0);',capture+'        pkt.buf = av_buffer_create(pkt.data, pkt.size, decklink_object_free, videoFrame, 0);')
edit('libavdevice/decklink_dec.cpp','if (ctx->spank_scte104_failed)', '    if (ctx->spank_scte && ctx->spank_scte->failed.load())', '    if (__atomic_load_n(&ctx->spank_scte104_failed, __ATOMIC_ACQUIRE)) return AVERROR_INVALIDDATA;\n    if (ctx->spank_scte && ctx->spank_scte->failed.load())')
edit('libavdevice/decklink_enc_c.c','"spankvanc_scte_output"', '    { "spankvanc_caption_output",', '''    { "spankvanc_scte_output", "SCTE-104 output: 0 strip, 1 pass SDI, 2 convert SCTE-35", OFFSET(spankvanc_scte_output), AV_OPT_TYPE_INT, { .i64 = 0 }, 0, 2, ENC },
    { "spankvanc_scte_output_strict", "Stop on rejected SCTE-35 cue", OFFSET(spankvanc_scte_output_strict), AV_OPT_TYPE_BOOL, { .i64 = 0 }, 0, 1, ENC },
    { "spankvanc_caption_output",''')
edit('libavdevice/decklink_enc.cpp','"spankvanc_scte35_to104.hpp"', '/* DeckLink callback class declaration */', '#include "spankvanc_scte35_to104.hpp"\n\n/* DeckLink callback class declaration */')
edit('libavdevice/decklink_enc.cpp','->spankvanc_scte_output) {', ')->spankvanc_caption_output) {', ')->spankvanc_caption_output || ((struct decklink_cctx *)avctx->priv_data)->spankvanc_scte_output) {')
edit('libavdevice/decklink_enc.cpp','// SpankVANC converter lifecycle', '    cctx->ctx = ctx;', '''    cctx->ctx = ctx;
    // SpankVANC converter lifecycle
    if (cctx->spankvanc_scte_output == 2) ctx->spank_to104 = new spankvanc::Scte35To104;
''')
edit('libavdevice/decklink_enc.cpp','delete ctx->spank_to104;', '    ff_decklink_cleanup(avctx);\n\n    if (ctx->output_callback)', '    delete ctx->spank_to104; ctx->spank_to104 = NULL;\n    ff_decklink_cleanup(avctx);\n\n    if (ctx->output_callback)')
# Header failures have a separate cleanup path.
edit('libavdevice/decklink_enc.cpp','// SpankVANC converter header cleanup', 'error:\n    ff_decklink_cleanup(avctx);', 'error:\n    delete ctx->spank_to104; ctx->spank_to104 = NULL; // SpankVANC converter header cleanup\n    ff_decklink_cleanup(avctx);')
edit('libavdevice/decklink_enc.cpp','case AV_CODEC_ID_SCTE_35:', '    case AV_CODEC_ID_SMPTE_2038:', '''    case AV_CODEC_ID_SCTE_35:
        if (((struct decklink_cctx *)avctx->priv_data)->spankvanc_scte_output == 2) ret = 0;
        break;
    case AV_CODEC_ID_SMPTE_2038:''')
helper='''// SpankVANC primary-stream SCTE-104 VANC insertion.
static int spank_insert104(struct decklink_ctx *ctx, struct klvanc_line_set_s *lines,
                           const std::vector<spankvanc::Anc104>& packets)
{
    return spankvanc::insert104(ctx->vanc_ctx, lines, packets);
}

'''
p=root/'libavdevice/decklink_enc.cpp';text=p.read_text()
if '// SpankVANC primary-stream SCTE-104 VANC insertion.' in text:
 begin=text.index('// SpankVANC primary-stream SCTE-104 VANC insertion.')
 end=text.index('static int decklink_construct_vanc(',begin)
 text=text[:begin]+helper+text[end:]
 p.write_text(text)
edit('libavdevice/decklink_enc.cpp','"spankvanc_scte_vanc.hpp"','#include "spankvanc_scte35_to104.hpp"','#include "spankvanc_scte35_to104.hpp"\n#include "spankvanc_scte_vanc.hpp"')
edit('libavdevice/decklink_enc.cpp','// SpankVANC primary-stream SCTE-104 VANC insertion.', 'static int decklink_construct_vanc(', helper+'static int decklink_construct_vanc(')
edit('libavdevice/decklink_enc.cpp','// SpankVANC insert exact source ANC', '    construct_afd(avctx, ctx, pkt, &vanc_lines, st);', '''    construct_afd(avctx, ctx, pkt, &vanc_lines, st);
    // SpankVANC insert exact source ANC on its source frame and line.
    if (((struct decklink_cctx *)avctx->priv_data)->spankvanc_scte_output == 1) {
        size_t size = 0;
        const uint8_t *data = av_packet_get_side_data(pkt, AV_PKT_DATA_SPANKVANC_SCTE104, &size);
        if (data) {
            try { ret = spank_insert104(ctx, &vanc_lines, spankvanc::unpack104(data, size)); }
            catch (const std::exception& e) { av_log(avctx, AV_LOG_ERROR, "SCTE-104 side data: %s\\n", e.what()); ret = AVERROR_INVALIDDATA; }
            if (ret) { for (int j=0;j<vanc_lines.num_lines;++j) klvanc_line_free(vanc_lines.lines[j]); return ret; }
        }
    }''')
# PCR-stamped TS data can legitimately precede video PTS. Never discard it as a stale ANC frame.
edit('libavdevice/decklink_enc.cpp','// SpankVANC SCTE-35 PCR queue', '        if (vanc_pkt.pts + 1 < ctx->last_pts) {', '''        // SpankVANC SCTE-35 PCR queue
        if (avctx->streams[vanc_pkt.stream_index]->codecpar->codec_id != AV_CODEC_ID_SCTE_35 && vanc_pkt.pts + 1 < ctx->last_pts) {''')
conversion='''        // SpankVANC SCTE-35 -> 104 at the containing video frame's clock.
        if (vanc_st->codecpar->codec_id == AV_CODEC_ID_SCTE_35 && ctx->spank_to104) {
            try {
                int64_t frame90k = av_rescale_q(pkt->pts, st->time_base, AVRational{1,90000});
                auto message = ctx->spank_to104->convert(spankvanc::Bytes(vanc_pkt.data, vanc_pkt.data+vanc_pkt.size), frame90k);
                if (!message.empty()) ret = spank_insert104(ctx, &vanc_lines, spankvanc::fragment104(message));
            } catch (const std::exception& e) {
                av_log(avctx, AV_LOG_WARNING, "SCTE-35 -> 104 cue rejected: %s\\n", e.what());
                const char *hex="0123456789abcdef"; std::string payload;
                for (int k=0;k<vanc_pkt.size && k<4096;++k) { payload+=hex[vanc_pkt.data[k]>>4]; payload+=hex[vanc_pkt.data[k]&15]; }
                av_log(avctx, AV_LOG_WARNING, "SPANKVANC_SCTE_REJECT {\\"reason\\":\\"%s\\",\\"payload_hex\\":\\"%s\\",\\"source_pts90k\\":%lld}\\n",e.what(),payload.c_str(),(long long)av_rescale_q(pkt->pts, st->time_base, AVRational{1,90000}));
                if (((struct decklink_cctx *)avctx->priv_data)->spankvanc_scte_output_strict) ret=AVERROR_INVALIDDATA;
            }
        }
'''
edit('libavdevice/decklink_enc.cpp','// SpankVANC SCTE-35 -> 104 at', '        av_packet_unref(&vanc_pkt);\n    }\n\n    IDeckLinkVideoFrameAncillary *vanc;', conversion+'''        av_packet_unref(&vanc_pkt);
        if (ret) { for (int j=0;j<vanc_lines.num_lines;++j) klvanc_line_free(vanc_lines.lines[j]); return ret; }
    }

    IDeckLinkVideoFrameAncillary *vanc;''')
# Never silently drop a cue because its VANC line could not be emitted.
edit('libavdevice/decklink_enc.cpp','// SpankVANC fail on VANC line loss', '            continue;\n        }\n\n        /* Generate the full line', '            vanc->Release(); ret = AVERROR(EIO); goto done; // SpankVANC fail on VANC line loss\n        }\n\n        /* Generate the full line')
edit('libavdevice/decklink_enc.cpp','// SpankVANC fail on line generation', '            av_log(avctx, AV_LOG_ERROR, "Failed to generate VANC line\\n");\n            continue;', '            av_log(avctx, AV_LOG_ERROR, "Failed to generate VANC line\\n");\n            vanc->Release(); ret = AVERROR(EIO); goto done; // SpankVANC fail on line generation')
print('SCTE-104 passthrough and SCTE-35 SDI conversion patches installed')

# Upgrade the initial private patch in an already prepared source tree too.
p=root/'libavdevice/decklink_dec.cpp'
s=p.read_text().replace('ctx->spank_scte104_failed = 1;', '__atomic_store_n(&ctx->spank_scte104_failed, 1, __ATOMIC_RELEASE);').replace('if (ctx->spank_scte104_failed) return AVERROR_INVALIDDATA;', 'if (__atomic_load_n(&ctx->spank_scte104_failed, __ATOMIC_ACQUIRE)) return AVERROR_INVALIDDATA;')
p.write_text(s)
