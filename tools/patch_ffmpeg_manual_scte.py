"""Output-only manual cue journals for the pinned FFmpeg 7.0.2 engine."""
from pathlib import Path
import sys
root = Path(sys.argv[1])
project = Path(__file__).resolve().parent.parent

def edit(name, marker, old, new):
    p = root / name
    text = p.read_text()
    if marker in text:
        return
    if text.count(old) != 1:
        raise SystemExit('Unexpected manual SCTE insertion: ' + name + ': ' + old[:80])
    p.write_text(text.replace(old, new, 1))

for folder in ('libavformat', 'libavdevice'):
    (root / folder / 'spankvanc_manual_scte.h').write_bytes((project / 'native/manual_scte.h').read_bytes())
edit('libavformat/mpegtsenc.c', '#include "spankvanc_manual_scte.h"', 'typedef struct MpegTSWrite {', '#include "spankvanc_manual_scte.h"\n\ntypedef struct MpegTSWrite {')
edit('libavformat/mpegtsenc.c', 'char *spankvanc_manual_scte;', '    const AVClass *av_class;', '    const AVClass *av_class;\n    char *spankvanc_manual_scte;\n    FILE *spank_manual_file;\n    int spank_manual_cc;')
edit('libavformat/mpegtsenc.c', 'spank_manual_open(&ts->', '    if (ts->m2ts_mode == -1) {', '''    if (ts->spankvanc_manual_scte) {
        int error = spank_manual_open(&ts->spank_manual_file, ts->spankvanc_manual_scte);
        if (error < 0) return error;
        if (s->nb_programs || ts->m2ts_mode == 1) return AVERROR(EINVAL);
    }
    if (ts->m2ts_mode == -1) {''')
edit('libavformat/mpegtsenc.c', '// SpankVANC manual CUEI', '    /* put program info here */', '''    /* put program info here */
    // SpankVANC manual CUEI registration.
    if (ts->spankvanc_manual_scte)
        put_registration_descriptor(&q, MKTAG('C','U','E','I'));''')
edit('libavformat/mpegtsenc.c', '// SpankVANC manual PID', '    if (err)\n        av_log(s, AV_LOG_ERROR,', '''    // SpankVANC manual PID is reserved for an output-only cue stream.
    if (ts->spankvanc_manual_scte) {
        if (q + 8 > data + sizeof(data)) return AVERROR_INVALIDDATA;
        *q++ = 0x86; put16(&q, 0xe000 | 0x1ffe);
        put16(&q, 0xf003); *q++ = 0x8a; *q++ = 1; *q++ = 1;
    }
    if (err)
        av_log(s, AV_LOG_ERROR,''')
edit('libavformat/mpegtsenc.c', '// SpankVANC manual emission', '        return mpegts_write_packet_internal(s, pkt);', '''        // SpankVANC manual emission follows video, with a dedicated section PID.
        MpegTSWrite *ts = s->priv_data;
        int ret = mpegts_write_packet_internal(s, pkt);
        if (ret < 0 || !ts->spank_manual_file ||
            s->streams[pkt->stream_index]->codecpar->codec_type != AVMEDIA_TYPE_VIDEO) return ret;
        for (unsigned i = 0; i < s->nb_streams; ++i)
            if (((MpegTSWriteStream *)s->streams[i]->priv_data)->pid == 0x1ffe)
                return AVERROR(EINVAL);
        {
            uint8_t section[64];
            int size = spank_manual_read(ts->spank_manual_file, section);
            if (size < 0) return size;
            if (size) {
                MpegTSSection writer = {0};
                writer.pid = 0x1ffe; writer.cc = ts->spank_manual_cc;
                writer.write_packet = section_write_packet; writer.opaque = s;
                mpegts_write_section(&writer, section, size);
                ts->spank_manual_cc = writer.cc;
                av_log(s, AV_LOG_INFO, "SPANKVANC_MANUAL_SCTE emitted SCTE-35\\n");
            }
        }
        return ret;''')
edit('libavformat/mpegtsenc.c', '// SpankVANC close manual journal', '    MpegTSService *service;\n    int i;', '''    MpegTSService *service;
    int i;
    // SpankVANC close manual journal.
    if (ts->spank_manual_file) fclose(ts->spank_manual_file);
    ts->spank_manual_file = NULL;''')
edit('libavformat/mpegtsenc.c', '{ "spankvanc_manual_scte",', 'static const AVOption options[] = {', 'static const AVOption options[] = {\n    { "spankvanc_manual_scte", "Private output-only cue journal", OFFSET(spankvanc_manual_scte), AV_OPT_TYPE_STRING, { .str = NULL }, 0, 0, AV_OPT_FLAG_ENCODING_PARAM },')
# DeckLink consumes identical sections through the existing checked 35 -> 104 converter.
edit('libavdevice/decklink_common_c.h', 'char *spankvanc_manual_scte;', '    int spankvanc_scte_output;', '    int spankvanc_scte_output;\n    char *spankvanc_manual_scte;')
edit('libavdevice/decklink_common.h', 'FILE *spank_manual_file;', '    spankvanc::Scte35To104 *spank_to104;', '    spankvanc::Scte35To104 *spank_to104;\n    FILE *spank_manual_file;')
edit('libavdevice/decklink_enc_c.c', '{ "spankvanc_manual_scte",', '    { "spankvanc_scte_output",', '    { "spankvanc_manual_scte", "Private output-only cue journal", OFFSET(spankvanc_manual_scte), AV_OPT_TYPE_STRING, { .str = NULL }, 0, 0, ENC },\n    { "spankvanc_scte_output",')
edit('libavdevice/decklink_enc.cpp', '#include "spankvanc_manual_scte.h"', '#include "spankvanc_scte_vanc.hpp"', '#include "spankvanc_scte_vanc.hpp"\n#include "spankvanc_manual_scte.h"')
edit('libavdevice/decklink_enc.cpp', '// SpankVANC manual requires VANC', ')->spankvanc_scte_output) {', ')->spankvanc_scte_output || ((struct decklink_cctx *)avctx->priv_data)->spankvanc_manual_scte) { // SpankVANC manual requires VANC')
edit('libavdevice/decklink_enc.cpp', '// SpankVANC manual converter', '    if (cctx->spankvanc_scte_output == 2) ctx->spank_to104 = new spankvanc::Scte35To104;', '''    // SpankVANC manual converter and private journal.
    if (cctx->spankvanc_scte_output == 2 || cctx->spankvanc_manual_scte)
        ctx->spank_to104 = new spankvanc::Scte35To104;
    if (cctx->spankvanc_manual_scte) {
        int error = spank_manual_open(&ctx->spank_manual_file, cctx->spankvanc_manual_scte);
        if (error < 0) { delete ctx->spank_to104; ctx->spank_to104 = NULL; return error; }
    }''')
p=root/'libavdevice/decklink_enc.cpp';s=p.read_text()
if '// SpankVANC close manual files' not in s:
    s=s.replace('    delete ctx->spank_to104; ctx->spank_to104 = NULL;', '    // SpankVANC close manual files\n    if (ctx->spank_manual_file) fclose(ctx->spank_manual_file);\n    ctx->spank_manual_file = NULL;\n    delete ctx->spank_to104; ctx->spank_to104 = NULL;')
    p.write_text(s)
edit('libavdevice/decklink_enc.cpp', '// SpankVANC manual frame cue', '    construct_afd(avctx, ctx, pkt, &vanc_lines, st);', '''    construct_afd(avctx, ctx, pkt, &vanc_lines, st);
    // SpankVANC manual frame cue: output only, no input data stream required.
    if (ctx->spank_manual_file) {
        unsigned char section[64];
        int size = spank_manual_read(ctx->spank_manual_file, section);
        if (size < 0) ret = size;
        else if (size) {
            try {
                auto message = ctx->spank_to104->convert(spankvanc::Bytes(section, section+size), 0);
                if (message.empty()) ret = AVERROR_INVALIDDATA;
                else ret = spank_insert104(ctx, &vanc_lines, spankvanc::fragment104(message));
                if (!ret) av_log(avctx, AV_LOG_INFO, "SPANKVANC_MANUAL_SCTE emitted SCTE-104\\n");
            } catch (const std::exception& e) {
                av_log(avctx, AV_LOG_ERROR, "Manual SCTE conversion failed: %s\\n", e.what());
                ret = AVERROR_INVALIDDATA;
            }
        }
        if (ret) { for (int j=0;j<vanc_lines.num_lines;++j) klvanc_line_free(vanc_lines.lines[j]); return ret; }
    }''')
print('Manual output SCTE journals installed')
