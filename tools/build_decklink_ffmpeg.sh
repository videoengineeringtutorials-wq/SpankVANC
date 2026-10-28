#!/usr/bin/env bash
# Local use only: nonfree FFmpeg output must not be redistributed.
# Ubuntu: build a private FFmpeg; no sudo and no system package replacement.
set -euo pipefail
project_dir=$(cd "$(dirname "$0")/.." && pwd)
sdk_include=${1:?Usage: build_decklink_ffmpeg.sh /path/to/DeckLinkSDK/Linux/include}
revision=a23e094488f139522c0e175e9766212a1213e486
build_dir="$project_dir/build/ffmpeg-decklink"
mkdir -p "$build_dir/deps"
cd "$build_dir/deps"
if [ ! -f root/usr/include/x264.h ] || [ ! -f root/usr/include/openssl/ssl.h ]; then
  apt-get download libx264-dev libsrt-gnutls-dev libssl-dev nasm
  for package in ./*.deb; do dpkg-deb -x "$package" root; done
fi
# Link extracted development symlinks to already installed runtime libraries.
python3 - "$build_dir/deps/root/usr/lib/x86_64-linux-gnu" <<'PYDEPS'
from pathlib import Path
import sys
p = Path(sys.argv[1])
for link in p.glob('*.so'):
    if link.is_symlink() and not link.exists():
        target = Path('/usr/lib/x86_64-linux-gnu') / link.readlink().name
        if not target.exists():
            raise SystemExit(f'Missing runtime library: {target}')
        link.unlink()
        link.symlink_to(target)
# SRT shared linkage needs no private GnuTLS/nettle development headers.
pc = p / 'pkgconfig/srt.pc'
s = pc.read_text()
pc.write_text('\n'.join(line for line in s.splitlines() if not line.startswith('Requires.private:')) + '\n')
PYDEPS
cd "$build_dir"
if [ ! -d "FFmpeg-$revision" ]; then
  curl -fL --retry 2 "https://github.com/FFmpeg/FFmpeg/archive/$revision.tar.gz" -o source.tar.gz
  tar -xzf source.tar.gz
fi
python3 "$project_dir/tools/patch_ffmpeg_decklink.py" "$build_dir/FFmpeg-$revision"
python3 "$project_dir/tools/patch_ffmpeg_monitor_scte.py" "$build_dir/FFmpeg-$revision"
export PATH="$build_dir/deps/root/usr/bin:$PATH"
export PKG_CONFIG_LIBDIR="$build_dir/deps/root/usr/lib/x86_64-linux-gnu/pkgconfig"
export PKG_CONFIG_SYSROOT_DIR="$build_dir/deps/root"
cd "FFmpeg-$revision"
./configure --prefix="$build_dir" --enable-gpl --enable-nonfree --enable-version3 --stdcxx=c++17 --enable-decklink \
  --enable-libx264 --enable-libsrt --enable-openssl --disable-doc --disable-debug \
  --disable-ffplay --disable-autodetect --disable-outdevs \
  --extra-cflags="-I$sdk_include -I$build_dir/deps/root/usr/include/x86_64-linux-gnu" --extra-cxxflags="-I$sdk_include"
make -j4
make install
"$build_dir/bin/ffmpeg" -hide_banner -devices
