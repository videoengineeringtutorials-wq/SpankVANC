# SpankVANC project continuity

Start project work by reading `docs/PROJECT_HANDOFF.md` for the current release,
implementation map, verification limits and outstanding work. Read
`docs/SDI_SCTE.md` when working on caption/SCTE playout or conversion.

If `docs/WORKSTATION_HANDOFF.md` exists, read it for private deployment details
and the remote workstation context. It is intentionally gitignored and excluded
from public source/app archives. Do not copy its machine addresses, account or
SSH details into public documentation or release assets.

Check the existing working tree before editing. The 0.9.1 publication includes
the preceding 0.7–0.9 implementation and installation documentation.
Preserve unrelated work, saved routes, existing engines and running media paths.

Source checkout paths use `spankvanc/`, `native/`, `tools/`, and `windows/`.
The portable Windows app uses `app/spankvanc/`, `build-support/native/`,
`build-support/tools/`, and `app/windows_build_capture.py` instead.

Use the latest dated verification record when assessing readiness. Earlier
historical notes describing features as unimplemented may no longer apply.
Keep the locally built FFmpeg/SDK/driver binaries out of public packages;
`docs/REDISTRIBUTION.md` records the existing distribution policy.
