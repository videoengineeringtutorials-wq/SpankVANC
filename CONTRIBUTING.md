# Contributing

Work on a branch and open a pull request against the personal SpankVANC repository.
Report OS, card model, Desktop Video/FFmpeg version, source mode and minimal
reproduction. Use fake stream keys and scrub logs; never attach route settings,
SDK archives, driver installers or real broadcast captures without permission.

Use Python 3.11+ and run `python3 -m unittest discover -s tests -v`.
For media tests install ffmpeg/ffprobe, g++, pkg-config and libavformat/libavcodec/
libavutil development libraries. C++ bench tests use CMake/CTest. Browser tests
use Playwright and are separate from physical hardware tests.

Changes to timing, caption or TS handling need an independent decoded-media or
packet-level check. Keep source/receiver/hardware verification claims distinct.
See docs/TEST_RESULTS.md. Do not mask transport errors or silently drop required
metadata to make a route appear ready.

## Releases

Bump pyproject.toml and spankvanc/__init__.py together, update CHANGELOG.md and
run the checks. Build with `python3 tools/package_source.py` and
`python3 tools/package_windows.py`. Review both archives before publishing;
use only source and the app-only Windows ZIP plus their checksum files.
The Windows packager rejects FFmpeg-bundling arguments. Never upload old
Extended packages or local nonfree capture executables. Recheck exact upstream
license terms before changing the dependency inventory.

The manual **App-only release** Actions workflow accepts an existing version tag,
checks version consistency, reruns tests and builds audited source/app assets
into a **draft prerelease**. Review its notes/checksums before publishing. It
does not compile or attach FFmpeg or SDK files.
