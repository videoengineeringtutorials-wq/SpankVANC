"""Guard FFmpeg's AVClass-first context contract and repeatable patching."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PATCH=Path(__file__).resolve().parent.parent/'tools/patch_ffmpeg_playout.py'

class PlayoutPatchTests(unittest.TestCase):
    def test_context_class_stays_first_and_old_layout_is_repaired(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'libavcodec').mkdir();(root/'libavdevice').mkdir()
            (root/'libavcodec/v210enc.c').write_text('    *got_packet = 1;\n')
            (root/'libavdevice/decklink_enc_c.c').write_text('static const AVOption options[] = {\n};\n')
            header=root/'libavdevice/decklink_common_c.h'
            header.write_text('struct decklink_cctx {\n    const AVClass *cclass;\n};\n')
            (root/'libavdevice/decklink_enc.cpp').write_text('        ctx->supports_vanc = 0;\n'
                '        if (decklink_construct_vanc(avctx, ctx, pkt, frame, st))\n'
                '            av_log(avctx, AV_LOG_ERROR, "Failed to construct VANC\\n");\n')
            def run():subprocess.run([sys.executable,str(PATCH),str(root)],check=True,capture_output=True)
            run()
            first={p:p.read_text() for p in root.rglob('*') if p.is_file()}
            self.assertLess(header.read_text().index('const AVClass'),header.read_text().index('int spankvanc_caption_output'))
            run();self.assertEqual(first,{p:p.read_text() for p in first})
            header.write_text(header.read_text().replace('    int spankvanc_caption_output;\n','').replace(
                'struct decklink_cctx {\n','struct decklink_cctx {\n    int spankvanc_caption_output;\n'))
            run();self.assertEqual(header.read_text(),first[header])
