# Changelog

## 0.6.1 — guided Windows setup and local build

- Full PC-and-Blackmagic-card beginner guide with the user-suggested AnimMouse
  download option, x64 extraction, driver setup, first recording and troubleshooting.
- Build Extended Capture.cmd guides a local Ubuntu/WSL build using user-supplied
  SDK 12.8 files, then verifies the new engine and saves its path.
- Automated prerequisite installation, pinned/source-hash-checked downloads,
  SDK interface generation and static Windows FFmpeg build; resumable dependencies.
- App ZIP includes build helper/support source, not SDKs or capture binaries.
  Existing engines/settings are preserved and build products stay local.

## 0.6.0 — first public experimental release

- Dedicated YouTube progressive SDR 1080p30 profile: deinterlacing, square-pixel
  scaling/padding, H.264 High CBR 14 Mbit/s, 2-second GOP, 2 B-frames / 1 reference,
  AAC-LC stereo 44.1 kHz / 128 kbit/s. TS output settings remain independent.
- Probe required YouTube filters and RTMPS in the selected FFmpeg.
- Default UDP datagrams to 1316 bytes; reject unaligned or oversized TS packet
  sizes. A live multicast report remains open for receiver-side validation.
- Separate prefilled YouTube server and masked stream key; migrate older routes.
- Multiple SCTE commands in one MOM, descriptor scoping and atomic validation.
- Continue A/V on rejected SCTE messages by default; retained, bounded diagnostics
  and optional strict stop. Supported cues become proper TS sections with CRC,
  PMT signaling and output-clock adjustment; internal heartbeat nulls stay internal.
- Live CC1–CC4 source monitor and compatibility discovery for original Duo.
- Public source and Windows app-only distribution, setup/build documentation,
  licensing audit, checksums and automated checks. No FFmpeg/SDK/driver binaries.

## Earlier local development trials (0.1–0.5)

These were workstation trials, not public releases. Extended packages contained
an FFmpeg build configured nonfree and are not eligible as public assets.
The source history here begins with the reviewed 0.6.0 snapshot.
