# Sources and reuse

- Existing user project `CaptionGPT`: copied `captions_608.h` into
  `native/` for caption construction and the real-media test fixture. Its MIT
  license is retained as this checkout's `LICENSE` (Kale Garner, 2026).
- Existing `audioWhisper`: inspected `audioWhisper.py`, `STT.py`
  and README. No files were changed or imported at application startup. Live
  timestamped PCM integration remains future work.
- Existing DeckLink SDK Linux Include files: external
  DeckLink SDK headers and dispatch source used to compile the new original
  extraction diagnostic. SDK files are not redistributed in the source bundle.
- [Blackmagic DeckLink SDK manual](https://documents.blackmagicdesign.com/UserManuals/DeckLinkSDKManual.pdf)
  and the installed headers: frame ancillary packet interfaces, input callbacks,
  packet payload ownership and scheduled output APIs.
- [Blackmagic DeckLink technical specifications](https://www.blackmagicdesign.com/products/decklink/techspecs)
  and [Duo 2 specifications](https://www.blackmagicdesign.com/uk/developer/products/capture-and-playback/techspecs/W-DLK-25):
  hardware capability checks. Exact available card/driver behavior still needs testing.
- [FFmpeg device documentation](https://www.ffmpeg.org/ffmpeg-devices.html),
  the existing FFmpeg source and installed `ffmpeg -h` output: DeckLink support,
  `libklvanc`-dependent output behavior, A/53 caption handling and filter options.
- [FFmpeg format documentation](https://www.ffmpeg.org/ffmpeg-formats.html):
  MPEG-TS AAC framing/LATM flags and FLV carriage. Local encoder/source checks
  and real media tests verify H.264/MPEG-2 video and AAC-LC ADTS in TS.
- [YouTube caption requirements](https://support.google.com/youtube/answer/3068031?hl=en):
  embedded caption setup and caption track limitations. No live YouTube test performed.
- [libklvanc](https://github.com/stoth68000/libklvanc) and
  [libklscte35](https://github.com/stoth68000/libklscte35): candidate packet parsers
  and SCTE conversion libraries. References were inspected; no code from them
  is vendored or linked in this prototype. Evaluate API coverage and licensing
  before adding them as dependencies.
- [TSDuck user guide](https://tsduck.io/docs/tsduck.html): candidate TS analysis,
  signaling and splice-insertion tooling. Presence is detected by the UI;
  TSDuck is not yet part of the live routing path.

Technical references checked October 26, 2026. The local Sites skill was read
for the browser UI workflow. The local-only workflow was selected because the
application operates on workstation hardware; no Site was registered or published.

### DeckLink live input integration

- FFmpeg DeckLink input and SDK compatibility interfaces, pinned source:
  https://github.com/FFmpeg/FFmpeg/tree/a23e094488f139522c0e175e9766212a1213e486/libavdevice
- Legacy ST 334-1 608 field polarity cross-check (bit 7 set denotes first field):
  https://github.com/stoth68000/libklvanc/blob/master/src/core-packet-eia_608.c
- The local FFmpeg patch captures DID 0x61 / SDID 0x02 via the SDK packet API;
  CDP captions decoded by upstream FFmpeg take precedence when both are present.

### Source monitor and SCTE conversion

- ST 2010 fragmentation flags and SCTE-104 operation layouts were checked against
  the libklvanc implementation and its cited ST 2010 / SCTE-104 specifications:
  https://github.com/stoth68000/libklvanc/blob/master/src/core-packet-scte_104.c
- SCTE-35 short-section syntax, CRC and splice semantics were independently
  checked using TSDuck `tstabcomp` / `tstables`:
  https://github.com/tsduck/tsduck/blob/master/src/libtsduck/dtv/tables/scte/tsSpliceInformationTable.cpp
- The new independent `native/scte104.hpp` implements a declared program-splice
  subset. The private FFmpeg extension copies packet data from the existing
  capture callback and writes sections directly through the TS section writer;
  it does not wrap SCTE-35 sections in a private-data PES stream.
