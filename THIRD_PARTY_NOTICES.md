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
