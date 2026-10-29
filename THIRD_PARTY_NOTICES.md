# Third-party notices

SpankVANC's original application and independent helper code are under the MIT
license in LICENSE. The caption helper originates from Kale Garner's
MIT-licensed CaptionGPT project; its attribution is retained.

FFmpeg is a separate program. Patch scripts modify upstream FFmpeg sources;
those modified sources remain subject to upstream's applicable LGPL/GPL terms.
No FFmpeg binary, source archive or library is included in public app releases.

The Windows app ZIP includes the official CPython 3.14.10 embedded distribution.
Its complete Python/PSF and bundled-component notices remain at
`python/LICENSE.txt`; `PACKAGE.json` records the download URL and verified hash.
The root MIT license does not replace those notices.

Blackmagic Desktop Video and the DeckLink SDK, x264, OpenSSL, SRT, compiler
runtimes and development tools are separate dependencies, not bundled in the
public app package. Their licenses are described in
[the redistribution audit](docs/REDISTRIBUTION.md). Their upstream licenses
apply when obtaining, building or distributing them separately.

Local SDI playout builds use [libklvanc](https://github.com/stoth68000/libklvanc),
pinned to d6915e37067ef9680ef27bb8c12cb6bd743471d2, under LGPL-2.1.
Source and license remain in the local build directory. It is not bundled in
the app-only distribution.

Whisper replacement runs an optional, separately installed OpenAI Whisper
(MIT) and PyTorch runtime; these dependencies and model weights are not bundled.
The legacy audioWhisper/serial encoder scripts are neither modified nor bundled.

The guided Setup EXE is built with [NSIS](https://nsis.sourceforge.io/License),
which uses the zlib/libpng license with separately documented bundled components.
Its payload remains app-only. Python 3.13.12 for speech, Torch 2.7.1, Whisper
20250625, Ubuntu Base 24.04.5, models and any Microsoft C++ runtime are downloaded
locally from their upstream sources; their notices are retained in those
installations. The installer does not grant redistribution rights to the locally
built FFmpeg engine or the user-supplied Blackmagic SDK/driver.
