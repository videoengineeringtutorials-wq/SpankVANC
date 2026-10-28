# Build the Windows capture engine locally

For a Windows-first walkthrough, use [the beginner guide](WINDOWS_BEGINNER.md).
From the current Windows app package, **Build Extended Capture.cmd** automates
the dependency preparation and local build after WSL and SDK setup. The
standalone `tools/bootstrap_windows_capture.py` does the same preparation inside
Ubuntu; `--check-only` validates prerequisites without downloads/builds.
The detailed manual procedure below remains available for developers.

This is an advanced **Ubuntu 24.04 / WSL2 cross-build** for Windows x64 using
FFmpeg 7.0.2 and DeckLink SDK 12.8 include interfaces. It produces a local-use
nonfree executable; do not upload it or historical Extended ZIPs to GitHub.
See [the redistribution audit](REDISTRIBUTION.md). The public Windows app is a
separate package which points to your resulting executable.

The existing build was exercised on Ubuntu with MinGW GCC 13.2 POSIX and static
x264/SRT/OpenSSL libraries. WSL2 is a suggested build host, not a tested SDI
capture environment: run the resulting executable on Windows with Desktop Video.
The native source telemetry, SCTE conversion, multi-command MOM support and TS
section mux patches are applied by the checked-in build script.

## Prerequisites

Install build tools on your Ubuntu build host:

```bash
sudo apt-get update
sudo apt-get install build-essential git curl xz-utils cmake pkg-config nasm perl python3 \
  gcc-mingw-w64-x86-64-posix g++-mingw-w64-x86-64-posix \
  binutils-mingw-w64-x86-64 mingw-w64-tools libwine-dev
```

Obtain the **12.8 SDK** from Blackmagic and accept its terms yourself. Retain its
license. Only its `Win/include` files are needed here. New SDK versions may
change interfaces and are not a drop-in claim of compatibility with old drivers.
Ask Blackmagic for the older SDK if it is not in their download archive.
Drivers/Desktop Video are installed separately on the Windows capture machine.

From the project root, use a Bash session and absolute build paths:

```bash
project_dir="$PWD"
build_dir="$project_dir/build/windows-cross"
deps_dir="$build_dir/deps"
mkdir -p "$build_dir" "$deps_dir" "$build_dir/toolchain/usr/bin"
ln -sf /usr/bin/x86_64-w64-mingw32-gcc-posix "$build_dir/toolchain/usr/bin/x86_64-w64-mingw32-gcc"
ln -sf /usr/bin/x86_64-w64-mingw32-g++-posix "$build_dir/toolchain/usr/bin/x86_64-w64-mingw32-g++"
export PATH="$build_dir/toolchain/usr/bin:$PATH"
```

Those symlinks are for a fresh build tree using system-installed tools. Do not
replace an already prepared extracted toolchain's links unnecessarily.

## Generate SDK include files

Set the first path to your own unpacked SDK. Work on a local copy of Include:

```bash
sdk_win_include="/absolute/path/to/Blackmagic DeckLink SDK 12.8/Win/include"
mkdir -p "$build_dir/decklink-headers/include"
cp "$sdk_win_include/"*.idl "$sdk_win_include/DeckLinkAPIVersion.h" "$build_dir/decklink-headers/include/"
cd "$build_dir/decklink-headers/include"
for file in ./*.idl; do sed -i -e '$a\' "$file"; done
x86_64-w64-mingw32-widl --win64 -I/usr/include/wine/wine/windows -h -u DeckLinkAPI.idl
cd "$project_dir"
```

The Wine development files supply imported IDL definitions such as `unknwn.idl`,
which Ubuntu MinGW alone does not provide. The automated helper extracts the
`libwine-dev` package locally instead of installing the Wine runtime.

If your distribution names the program `widl`, use that executable with the same
arguments. Confirm `DeckLinkAPIVersion.h` reports `0x0c080000` and that
`DeckLinkAPI.h`, `DeckLinkAPI_i.c` and `DeckLinkAPIVersion.h` exist. Include files
are build inputs, not release assets. The tested earlier header mirror was
`nanake/decklink-headers` branch `SDK/12.8`, commit
`18de098c6db7b0079ec38583967ffe8c3d410a2b`; the SDK downloaded directly from
Blackmagic is the preferred source.

## Dependency sources and static builds

Fetch sources from their upstream locations; keep the pinned revisions and
licenses. Run these commands once in a fresh build tree:

```bash
cd "$build_dir"
curl -fL --retry 2 https://ffmpeg.org/releases/ffmpeg-7.0.2.tar.xz -o ffmpeg-7.0.2.tar.xz
tar -xf ffmpeg-7.0.2.tar.xz
git clone https://code.videolan.org/videolan/x264.git x264
git -C x264 checkout 0480cb05fa188d37ae87e8f4fd8f1aea3711f7ee
curl -fL --retry 2 https://github.com/openssl/openssl/archive/refs/tags/openssl-3.5.9.tar.gz -o openssl-3.5.9.tar.gz
tar -xf openssl-3.5.9.tar.gz
curl -fL --retry 2 https://github.com/Haivision/srt/archive/refs/tags/v1.5.4.tar.gz -o srt-1.5.4.tar.gz
tar -xf srt-1.5.4.tar.gz
cd x264
./configure --host=x86_64-w64-mingw32 --cross-prefix=x86_64-w64-mingw32- \
  --prefix="$deps_dir" --enable-static --disable-cli --disable-opencl
make -j4
make install
cd "$build_dir/openssl-openssl-3.5.9"
perl Configure mingw64 --cross-compile-prefix=x86_64-w64-mingw32- \
  --prefix="$deps_dir" --libdir=lib no-shared no-module no-tests no-apps no-docs no-legacy
make -j4 build_libs
make install_dev
cd "$project_dir"
cmake -S "$build_dir/srt-1.5.4" -B "$build_dir/srt-build" \
  -DCMAKE_TOOLCHAIN_FILE="$project_dir/windows/mingw-toolchain.cmake" \
  -DCMAKE_FIND_ROOT_PATH="/usr/x86_64-w64-mingw32;$deps_dir" \
  -DCMAKE_INSTALL_PREFIX="$deps_dir" -DCMAKE_BUILD_TYPE=Release \
  -DENABLE_SHARED=OFF -DENABLE_STATIC=ON -DENABLE_APPS=OFF \
  -DENABLE_TESTING=OFF -DENABLE_STDCXX_SYNC=ON \
  -DOPENSSL_ROOT_DIR="$deps_dir" -DOPENSSL_USE_STATIC_LIBS=TRUE -DUSE_ENCLIB=openssl
cmake --build "$build_dir/srt-build" -j4
cmake --install "$build_dir/srt-build"
bash tools/build_windows_capture.sh
```

The script isolates pkg-config to Windows libraries, applies patches idempotently,
uses C++17, enables the YouTube filters and disables GPU/SDI-output components.
It removes SRT's explicit shared GCC runtime import so compiler libraries can
link statically. The final configure license is nonfree/unredistributable;
build success does not authorize redistribution.

## Use your local executable

The result is `build/windows-cross/capture/bin/ffmpeg.exe`. Make it available on
your own Windows machine, keep Desktop Video installed there, and point
`settings.json`'s `decklink_ffmpeg_path` to it. The app-only ZIP does not include
this executable. See [setup](SETUP.md) for the settings example.

Run these from Windows, substituting your actual executable path:

```powershell
C:\SpankVANC-capture\ffmpeg.exe -version
C:\SpankVANC-capture\ffmpeg.exe -hide_banner -h demuxer=decklink
C:\SpankVANC-capture\ffmpeg.exe -hide_banner -filters
```

DeckLink options should include `spankvanc_anc`, `spankvanc_scte35` and
`spankvanc_scte_strict`. The YouTube filters include yadif, scale, pad, setsar,
fps and setfield. Select the actual detected device and mode in the app.

## Validation and limits

The original Duo / Desktop Video 12.8 has user-reported SDI capture and live
caption monitoring. Synthetic Windows tests under Wine exercise caption
pass/strip, SCTE section muxing, multiple commands in one MOM, cue rejection
recovery, progressive encoding and UDP datagram integrity. They cannot validate
Blackmagic COM hardware, actual VANC packets, multicast networking or YouTube
live stream health. See [test results](TEST_RESULTS.md) and verify your receiver.

SCTE conversion supports timestamp type 0. Multiple normal commands become
separate sections in source order; supplemental descriptors belong to their
preceding normal request. Entire messages are validated before output/dedupe
commit. Continue mode discards rejected messages and allows later valid cues;
strict mode stops. Resource/queue failures remain fatal.

## SDI caption output (0.7.0)

Rebuild the local engine even if a previous Extended engine is configured. The
build now pins libklvanc, enables the DeckLink output device and V210 encoder,
and copies A/53 frame side data to V210 packets for VANC generation. libklvanc
uses Autoconf, Automake and Libtool; the bootstrap dependency list includes them.
The app-only ZIP includes this build support, but no FFmpeg or SDK binaries.

Choose **DeckLink · SDI**, then select an actual detected output port and caption
**Pass through** or **Strip**. Choose **Strip** for SCTE. The output uses the
source format with embedded stereo 48 kHz PCM. Configure the connector for output
in Desktop Video Setup first; do not select the input port. Passthrough
regenerates 608/708 caption CDPs rather than copying all incoming ANC. If VANC
output cannot be enabled, passthrough stops with an error. Verify physical SDI
video, field order, audio and captions on the Windows/Duo workstation.

If firmware virtualization is unavailable, Ubuntu 24.04 under WSL 1 has also
been used to complete this cross-build. Native Windows engine execution,
DeckLink device discovery, V210 caption side data and pass/strip preflight
passed. Physical SDI output still requires downstream verification. The
build helper prefers the installed WSL executable and passes paths directly
to avoid the System32 launcher/quoting problems observed over SSH.

SCTE update (0.8.0): SDI outputs can Pass SCTE-104 from SDI input, or Convert
35 → 104 from a TS input. See docs/SDI_SCTE.md for PID selection, timing and
Continue/Stop behavior. Rebuild the local engine before enabling these choices.

Whisper update (0.9.0): current builds include the live CC1 replacement filter
and routed raw-audio tap. Configure a separate Whisper/PyTorch Python using
`whisper_python_path` in settings.json. CPU and CUDA are selectable. See
[Whisper setup and limits](WHISPER.md); A/V is not delayed by recognition.
