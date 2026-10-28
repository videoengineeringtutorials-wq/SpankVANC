#!/usr/bin/env bash
# Local use only: resulting nonfree FFmpeg binary must not be redistributed.
# Run on Ubuntu after preparing build/windows-cross (see WINDOWS_EXTENDED_BUILD.md).
# All dependencies and compiler files stay in build/, with no system installation.
set -euo pipefail
project_dir=$(cd "$(dirname "$0")/.." && pwd)
build_dir="$project_dir/build/windows-cross"
source_dir="$build_dir/ffmpeg-7.0.2"
export PATH="$build_dir/toolchain/usr/bin:$PATH"
export PKG_CONFIG_LIBDIR="$build_dir/deps/lib/pkgconfig"
export PKG_CONFIG_PATH=""
for item in "$source_dir/configure" "$build_dir/deps/lib/libx264.a" "$build_dir/deps/lib/libsrt.a" "$build_dir/deps/lib/libcrypto.a" "$build_dir/decklink-headers/include/DeckLinkAPI.h"; do
  test -f "$item" || { echo "Missing build prerequisite: $item" >&2; exit 1; }
done
# SRT's CMake metadata lists the compiler's shared GCC runtime explicitly.
# Remove that explicit import so -static-libgcc can provide the static runtime.
python3 - "$build_dir/deps/lib/pkgconfig/srt.pc" <<'PYSTATIC'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text();p.write_text(s.replace(' -lgcc_s',''))
PYSTATIC
python3 "$project_dir/tools/patch_ffmpeg_decklink.py" "$source_dir"
python3 "$project_dir/tools/patch_ffmpeg_monitor_scte.py" "$source_dir"
cd "$source_dir"
./configure --prefix="$build_dir/capture" --cross-prefix=x86_64-w64-mingw32- \
 --arch=x86_64 --target-os=mingw32 --enable-cross-compile --stdcxx=c++17 \
 --enable-gpl --enable-nonfree --enable-version3 --enable-static --disable-shared \
 --enable-decklink --disable-autodetect --disable-debug --disable-doc --disable-ffplay \
 --disable-w32threads --enable-pthreads --disable-outdevs --disable-everything \
 --enable-indev=decklink,lavfi --enable-libx264 --enable-libsrt --enable-openssl \
 --enable-encoder=libx264,mpeg2video,aac,pcm_s16le,wrapped_avframe \
 --enable-decoder=h264,mpeg2video,aac,rawvideo,v210,pcm_s16le,pcm_s32le \
 --enable-parser=h264,mpegvideo,aac,aac_latm \
 --enable-demuxer=mpegts,nut,flv,mov,matroska,rawvideo \
 --enable-muxer=mpegts,flv,null,nut,matroska \
 --enable-filter=buffer,buffersink,abuffer,abuffersink,format,scale,aresample,null,anull,sidedata,testsrc2,sine,setpts,asetpts,yadif,pad,setsar,fps,setfield \
 --enable-bsf=h264_mp4toannexb,aac_adtstoasc \
 --enable-protocol=file,pipe,tcp,udp,libsrt,rtmp,rtmps,tls,rtp \
 --extra-version=SpankVANC-Windows-SDK12.8 --pkg-config-flags=--static \
 --extra-cflags="-I$build_dir/decklink-headers/include" \
 --extra-cxxflags="-I$build_dir/decklink-headers/include" \
 --extra-ldflags="-static -static-libgcc -static-libstdc++"
touch fftools/ffmpeg.c fftools/ffprobe.c
make -j6
make install
