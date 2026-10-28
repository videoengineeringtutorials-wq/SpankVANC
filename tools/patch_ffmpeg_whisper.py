"""Register the private live 608 replacement filter in FFmpeg 7.0.2."""
from pathlib import Path
import shutil
import sys
root=Path(sys.argv[1])
shutil.copyfile(Path(__file__).resolve().parent.parent/'native/vf_spankvanc_cc.c',root/'libavfilter/vf_spankvanc_cc.c')
for name,needle,addition in (
    ('Makefile','OBJS-$(CONFIG_SIDEDATA_FILTER)', 'OBJS-$(CONFIG_SPANKVANC_CC_FILTER) += vf_spankvanc_cc.o\n'),
    ('allfilters.c','extern const AVFilter ff_vf_sidedata;', 'extern const AVFilter ff_vf_spankvanc_cc;\n')):
    p=root/'libavfilter'/name;s=p.read_text()
    if addition.strip() not in s:
        at=s.index(needle);s=s[:at]+addition+s[at:];p.write_text(s)
