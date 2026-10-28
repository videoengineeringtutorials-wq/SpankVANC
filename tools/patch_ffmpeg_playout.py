"""Preserve decoded A/53 captions through V210 into libklvanc SDI playout."""
from pathlib import Path
import sys
root = Path(sys.argv[1])
p = root / 'libavcodec/v210enc.c'
s = p.read_text()
marker = '/* SpankVANC V210 caption side data */'
if marker not in s:
    needle = '    *got_packet = 1;'
    if s.count(needle) != 1:
        raise SystemExit('Unsupported V210 encoder source')
    s = s.replace(needle, '''    /* SpankVANC V210 caption side data */
    const AVFrameSideData *cc = av_frame_get_side_data(pic, AV_FRAME_DATA_A53_CC);
    if (cc) {
        uint8_t *data = av_packet_new_side_data(pkt, AV_PKT_DATA_A53_CC, cc->size);
        if (!data)
            return AVERROR(ENOMEM);
        memcpy(data, cc->data, cc->size);
    }
''' + needle)
    p.write_text(s)
p = root / 'libavdevice/decklink_enc_c.c'
s = p.read_text()
if 'spankvanc_caption_output' not in s:
    needle = 'static const AVOption options[] = {'
    if s.count(needle) != 1:
        raise SystemExit('Unsupported DeckLink output options')
    s = s.replace(needle, needle + '''
#if CONFIG_LIBKLVANC
    { "spankvanc_caption_output", "SpankVANC V210 A/53 VANC playout", OFFSET(spankvanc_caption_output), AV_OPT_TYPE_BOOL, { .i64 = 0 }, 0, 1, ENC },
#endif''')
    p.write_text(s)

p = root / 'libavdevice/decklink_common_c.h'
s = p.read_text()
# FFmpeg requires the AVClass pointer to remain the first context member.
s = s.replace('struct decklink_cctx {\n    int spankvanc_caption_output;\n', 'struct decklink_cctx {\n')
if 'int spankvanc_caption_output;' not in s:
    needle = '    const AVClass *cclass;'
    if s.count(needle) != 1:
        raise SystemExit('Unsupported DeckLink context layout')
    s = s.replace(needle, needle + '\n    int spankvanc_caption_output;')
p.write_text(s)
p = root / 'libavdevice/decklink_enc.cpp'
s = p.read_text()
if 'SpankVANC requires VANC' not in s:
    needle = '        ctx->supports_vanc = 0;'
    s = s.replace(needle, '        if (((struct decklink_cctx *)avctx->priv_data)->spankvanc_caption_output) {\n            av_log(avctx, AV_LOG_ERROR, "SpankVANC requires VANC for caption passthrough\\n");\n            return AVERROR(EIO);\n        }\n' + needle, 1)
    old = '        if (decklink_construct_vanc(avctx, ctx, pkt, frame, st))\n            av_log(avctx, AV_LOG_ERROR, "Failed to construct VANC\\n");'
    new = '        if (decklink_construct_vanc(avctx, ctx, pkt, frame, st)) {\n            av_log(avctx, AV_LOG_ERROR, "Failed to construct VANC\\n");\n            frame->Release();\n            return AVERROR(EIO);\n        }'
    if old not in s:
        raise SystemExit('Unsupported VANC construction source')
    s = s.replace(old, new)
    p.write_text(s)
