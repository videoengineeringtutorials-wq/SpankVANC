# Redistribution audit and release policy

Reviewed 2026-10-27 against the actual build configuration and vendor terms.
This records the project's release decisions; it is not a blanket legal clearance
for other builds or a substitute for reviewing the licenses you actually use.

## Local build automation and third-party download links

**Build Extended Capture.cmd** invokes a local Ubuntu/WSL bootstrap, using SDK
Include files supplied by the user. It does not download/accept the SDK or
publish build results. Compiler packages and pinned open-source dependencies
and the Wine development IDL imports are obtained on that local machine. The same unredistributable-binary rule
applies to its output; automation is not an exemption.

The beginner guide links the user-suggested
[AnimMouse releases](https://github.com/AnimMouse/ffmpeg-stable-autobuild/releases).
That project explicitly describes its builds as nonfree, with DeckLink and
FDK AAC. We neither mirror them nor certify their redistribution compliance.
Their stock builds do not include SpankVANC extensions. Users review the
third-party notices and obtain their chosen engine separately.

## Public release contents

Publish SpankVANC's source, setup/build instructions and an app-only Windows ZIP
containing the official CPython embedded runtime and its intact license notices.
Do not upload historical Extended ZIPs, capture binaries, SDK bundles, driver
installers, local routes, logs, recordings or stream keys. The public packager
rejects FFmpeg-bundling arguments. Users obtain media dependencies separately
and build the capture extension locally when needed.

## DeckLink and FFmpeg: two different questions

Blackmagic's [current SDK agreement](https://www.blackmagicdesign.com/support/modal/download-with-terms-start/bmd-decklink-sdk)
section 0.1 exempts files in the Mac/Win/Linux Include folders from specified
clauses; it does not exempt every SDK file or the documentation. Other SDK files
remain subject to the agreement, including conditional sublicensing and sample
code restrictions. Review the terms shipped with your particular SDK version.
This project does not redistribute the SDK or Desktop Video installers.

The 12.8 include-only mirror used for the experimental cross-build has a
permissive Blackmagic notice; that is a file-specific notice, not permission to
redistribute the full SDK. Obtain the original SDK from Blackmagic for a local
build and retain its notices. A mirror is not proof of permission for unrelated
SDK files.

Separately, upstream FFmpeg **7.0.2** lists `decklink` and `libfdk_aac` in
`EXTERNAL_LIBRARY_NONFREE_LIST`. Enabling DeckLink with libx264 requires
`--enable-nonfree`. Its configure output labels the result nonfree and
unredistributable. This is the pinned configuration we actually use; do not
remove or bypass that check to claim a distributable binary.

The old 0.2–0.5 Extended packages contained this capture build. Describing them
as private trials did not establish redistribution rights. They must not become
GitHub release assets. Rebuild locally for use on your own systems. A future
public capture binary requires a separately reviewed architecture/configuration
and all applicable source/notice obligations, not just adding a license file.

Sources: [FFmpeg 7.0.2 configure](https://github.com/FFmpeg/FFmpeg/blob/n7.0.2/configure),
[FFmpeg license](https://github.com/FFmpeg/FFmpeg/blob/n7.0.2/LICENSE.md),
[FFmpeg legal guidance](https://ffmpeg.org/legal.html).

## Component inventory

| Component | Relevant license / condition | Release decision |
| --- | --- | --- |
| SpankVANC app, independent native helpers, firmware | MIT, see LICENSE | Source and app code included |
| FFmpeg patches | Changes to upstream FFmpeg; resulting modified FFmpeg follows its applicable LGPL/GPL terms | Patch/build scripts only, no FFmpeg binaries/source tree bundled |
| CPython 3.14.10 embedded x64 | PSF/Python license and bundled component notices in official LICENSE.txt | Include unmodified official runtime and intact notices; verified SHA-256 recorded |
| DeckLink SDK / Desktop Video | Version-specific Blackmagic agreement; include-file exception is scoped | Download separately; no SDK or driver archive bundled |
| FFmpeg 7.0.2 capture build | Nonfree/unredistributable configuration | Local build only; excluded from public assets |
| x264 | GPL-2.0-or-later | Local dependency; no binaries bundled; a distributable GPL build would require corresponding source and notices |
| OpenSSL 3.5.9 | Apache-2.0 | Local dependency; no binaries bundled; GPL combinations need compatible versions/options |
| SRT 1.5.4 | MPL-2.0 and third-party notices | Local dependency; no binaries bundled; preserve applicable source/notice obligations in any future redistribution |
| MinGW-w64 / GCC runtimes | Multiple notices and runtime exceptions | Build tools/local dependencies only; do not assume one license covers the toolchain |
| Existing user FFmpeg | Depends on its exact configuration, including nonfree libraries | User supplied; detecting it does not certify its redistribution rights |
| TSDuck, Wine, Playwright, FFmpeg dev libraries | Separate tool licenses | Optional development/test tools, excluded from app/source assets |
| Whisper/models, NVIDIA, other SDKs | Not used by this release | No models, GPU runtime, NVENC SDK or transcription engine included |

Codec patent licensing is separate from copyright/open-source licenses and varies
by use and jurisdiction. This project does not grant codec patent rights.

## Before any public release

1. Run tests and build the source/app-only packages using the checked-in tools.
2. Confirm assets contain no FFmpeg executables, SDK files, state or credentials.
3. Keep CPython's license and package origin/hash manifest intact.
4. Publish checksums, release notes, tested hardware and known limitations.
5. If introducing a binary dependency later, review its exact build, license,
   notices and corresponding-source requirements before adding it to packaging.
