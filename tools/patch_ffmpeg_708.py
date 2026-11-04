"""Generated-caption service announcements on DeckLink CDP/VANC output."""
from pathlib import Path
import sys
root=Path(sys.argv[1]);project=Path(__file__).resolve().parent.parent

def edit(name,marker,old,new):
    p=root/name;s=p.read_text()
    if marker in s:return
    if s.count(old)!=1:raise SystemExit('Unexpected 708 insertion: '+name+': '+old[:60])
    p.write_text(s.replace(old,new,1))

(root/'libavdevice/spankvanc_caption_services.h').write_bytes((project/'native/caption_services.h').read_bytes())
edit('libavdevice/decklink_common_c.h','int spankvanc_caption_format;', '    int spankvanc_caption_output;', '    int spankvanc_caption_output;\n    int spankvanc_caption_format;\n    char *spankvanc_caption_language;')
edit('libavdevice/decklink_enc_c.c','"spankvanc_caption_format"', '    { "spankvanc_caption_output",', '''    { "spankvanc_caption_format", "Generated CDP services: 0 source, 1 608, 2 708, 3 both", OFFSET(spankvanc_caption_format), AV_OPT_TYPE_INT, { .i64 = 0 }, 0, 3, ENC },
    { "spankvanc_caption_language", "Generated caption ISO-639-2 language", OFFSET(spankvanc_caption_language), AV_OPT_TYPE_STRING, { .str = "und" }, 0, 0, ENC },
    { "spankvanc_caption_output",''')
edit('libavdevice/decklink_enc.cpp','"spankvanc_caption_services.h"', 'static void construct_cc(', '#include "spankvanc_caption_services.h"\n\nstatic void construct_cc(')
edit('libavdevice/decklink_enc.cpp','// SpankVANC generated service info', '    klvanc_finalize_EIA_708B(cdp, ctx->cdp_sequence_num++);', '''    // SpankVANC generated service info; passthrough never invents services.
    struct decklink_cctx *cctx = (struct decklink_cctx *)avctx->priv_data;
    spank_caption_services(cdp, cctx->spankvanc_caption_format, cctx->spankvanc_caption_language);
    klvanc_finalize_EIA_708B(cdp, ctx->cdp_sequence_num++);''')
print('Native 708 caption service announcements installed')
