Historical Extended package note

The earlier workstation ZIPs bundled an FFmpeg 7.0.2 DeckLink build configured
with --enable-nonfree. They are not public release artifacts and must not be
uploaded or redistributed. The public packager no longer accepts capture
binaries, even when a build is described as private.

Use README.txt and docs/SETUP.md for the current app-only release.
For extended captions/SCTE, build the capture executable locally using
this project's scripts and docs/WINDOWS_EXTENDED_BUILD.md, then configure
its path. Read docs/REDISTRIBUTION.md before changing dependency packaging.
