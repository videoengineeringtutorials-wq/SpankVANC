# Live audioWhisper caption replacement (0.9.1)

Select **audioWhisper · replace** under Captions on each desired output. Other
outputs can still pass or strip independently. SCTE selection is independent.
The generated captions are CC1, field 1, two-row roll-up at row 15, with 32-column
word-boundary wrapping, odd parity and duplicated control commands. Roll-up
mode and explicit column zero are refreshed per line for joining/reacquiring
receivers; ordinary words are not split across rows. A single token longer
than 32 characters is split without discarding any characters. A/53 captions are replaced
on that output, then encoded into H.264/MPEG-2 or regenerated SDI VANC CDPs by the
existing local playout engine. Native 708 services are not generated.

The same FFmpeg process opens DeckLink once and taps its selected embedded
stereo channel to mono 16 kHz PCM. No OBS, Windows microphone device index,
`--devices true`, serial port or external EEG encoder is needed. TS inputs also
use their routed program audio. Select channel 1 or 2; a missing audio stream or
unavailable channel fails the route instead of silently generating no captions.

## Local setup

Rebuild the Extended engine using current build support. Version 0.9.1 requires the corrected continuous-framing filter; the 0.9.0
engine is insufficient for replacement. Replacement routes
use this local capture engine even for TS → TS. Existing unmodified FFmpeg
installations remain usable for other routes, but cannot inject live captions.
The capability panel and preflight detect the required filter.

Use a separate Python with `openai-whisper`, NumPy and PyTorch installed.
On portable Windows, set `whisper_python_path` in the app's `settings.json` to
that Python executable. An existing working installation can be used unchanged.
On Linux set `SPANKVANC_WHISPER_PYTHON` to the Python executable. The standalone
worker is launched by file path, so SpankVANC need not be installed in that
Python. Models use Whisper's normal local cache; first use can download a model.
No cloud transcription service or API key is used.

**Auto** uses CUDA when available. **CPU** forces CPU. **GPU · CUDA required**
fails preflight when CUDA is unavailable; it does not silently fall back.
Available model names depend on the installed Whisper version. The P6000 is
user-confirmed working with the existing Whisper installation. Video encoding
remains CPU-based; this selection controls speech recognition only.

## Windows installation from scratch

The [0.11.0 guided setup](WINDOWS_INSTALLER.md) automates an isolated CPU speech
installation and small.en model download. The manual steps below remain available.
Installer-created settings also include `whisper_model_cache`, which keeps its
models separate from another Whisper installation.

This is optional. Skip it for caption passthrough or stripping. Finish the
[Windows beginner guide](WINDOWS_BEGINNER.md), including the **0.9.1 local
extended engine build**, before testing generated captions.

1. Install a separate **64-bit Python 3.11** from
   [Python's Windows downloads](https://www.python.org/downloads/windows/).
   Include pip and the Python launcher. The app's embedded Python is for the
   control panel; do not install Whisper into its `python` folder.
2. Open **PowerShell** from Start. Check `py -3.11 --version`. Create a separate
   environment under your user folder, then install CPU PyTorch and Whisper:

   ```powershell
   py -3.11 -m venv "$env:USERPROFILE\SpankVANC-Whisper"
   & "$env:USERPROFILE\SpankVANC-Whisper\Scripts\python.exe" -m pip install --upgrade pip
   & "$env:USERPROFILE\SpankVANC-Whisper\Scripts\python.exe" -m pip install torch --index-url https://download.pytorch.org/whl/cpu
   & "$env:USERPROFILE\SpankVANC-Whisper\Scripts\python.exe" -m pip install openai-whisper numpy
   ```

   These commands install into the new environment without changing an existing
   Whisper installation. This is a starting recipe, not a pinned dependency set
   verified on every fresh PC. For package build errors, consult the
   [official Whisper setup instructions](https://github.com/openai/whisper#setup).
   SpankVANC supplies raw PCM directly; its worker does not invoke Whisper's
   command-line audio-file loader.
3. Verify imports and print the exact Python path:

   ```powershell
   & "$env:USERPROFILE\SpankVANC-Whisper\Scripts\python.exe" -c "import sys, whisper, numpy, torch; print(sys.executable); print('CUDA:', torch.cuda.is_available())"
   ```

   `CUDA: False` is expected with this CPU install. If the command fails,
   resolve the reported package problem before starting a replacement route.
4. With SpankVANC stopped, open **settings.json** beside **Start SpankVANC.cmd**
   in Notepad. Preserve its existing fields and add `whisper_python_path` with
   the path printed above. JSON needs doubled backslashes, for example:

   ```json
   {
     "ffmpeg_path": "C:\\Tools\\FFmpeg\\ffmpeg.exe",
     "decklink_ffmpeg_path": "C:\\Tools\\SpankVANC-Windows\\capture-ffmpeg-local\\your-built-engine.exe",
     "whisper_python_path": "C:\\Users\\YOURNAME\\SpankVANC-Whisper\\Scripts\\python.exe"
   }
   ```

   This illustrates the format; keep your actual engine paths. Add a comma
   between fields, with no trailing comma after the final field. Save as
   `settings.json`, not `settings.json.txt`.
5. Download the initial model before starting a route (first download needs
   Internet and may exceed the app's startup timeout):

   ```powershell
   & "$env:USERPROFILE\SpankVANC-Whisper\Scripts\python.exe" -c "import whisper; whisper.load_model('small', device='cpu'); print('Model cached')"
   ```

6. Start SpankVANC again. On one test output select **audioWhisper · replace**,
   model **small**, device **CPU**, and the embedded audio channel carrying
   speech. Check route readiness, start, and inspect the Engine log and a
   downstream CC1 receiver. If inference falls behind, try `base` or `tiny`
   (cache the matching model first). Stop the test before changing settings.

For NVIDIA acceleration, use the [official PyTorch installation selector](https://pytorch.org/get-started/locally/)
for Windows/Pip and a CUDA build compatible with your GPU and driver. Run its
install command using the same environment's Python (`python.exe -m pip` in
place of `pip`), then repeat the import check. Choose **GPU · CUDA required**
only when `torch.cuda.is_available()` returns true. Older GPUs may need older
supported PyTorch builds; the workstation's existing P6000 environment does not
establish compatibility with today's default packages. Cache the model you
intend to use, for example `turbo`, before testing. CPU video encoding is
unchanged. Existing working Whisper environments can be used directly instead
of creating another one.


## Timing and operational limits

Audio is recognized in three-second chunks. Captions arrive after chunk capture,
model inference and paced 608 transmission. A/V continues live without delay;
this mode does not promise speech-synchronous captions. An external delay can
be used for alignment when it delays program A/V relative to the caption path.
Delaying captions and A/V equally preserves their existing offset. The old `delay_ms`
configuration field is retained for compatibility and ignored; the placeholder
program-delay control has been removed.

Inference has a three-chunk bounded queue. Slow inference drops audio with an
engine-log warning; excessive caption backlog drops a transcript to keep output
live. Choose a smaller model when needed. Silence suppresses recognition, and
an erase command clears displayed text after an idle interval. Recognition can
still make errors or hallucinate. Basic 608 characters are transliterated where
possible; unsupported glyphs become `?`.

The private `runtime/whisper/cc1.pairs` journal is reset on each start and holds
only generated caption bytes. It is capped at 64 MiB per route. Each replacement
output reads it independently. Field-1 CC1 pairs are paced at 25 or 29.97/30
pairs per second, with null field-2 slots and invalid 708 padding continuously
present, including silence. The frame-rate-specific A/53 tuple budget is fixed
(for example, 20 tuples per frame at 29.97/30 fps and 10 at 59.94/60 fps). The worker must load before
capture starts. Worker failure stops the route to avoid silent caption loss.

Verify generated CC1 on the downstream SDI receiver and TS decoder before using
it operationally. Synthetic parity, pacing, codec and application checks do not
establish acceptance by a particular physical receiver.

## Output carriage and 0.9.0 receiver report

TS H.264 carries A/53 bytes in registered SEI; MPEG-2 uses video user data.
YouTube uses H.264 SEI in FLV at 30 fps. SDI copies those caption bytes through
V210 packet side data into a VANC CDP using the existing libklvanc path. These
are separate outer formats; the generated 608 commands and field slots must
be valid before either outer format is constructed.

The user reported that 0.9.0 was detected as 608 on the Leader but did not render,
and YouTube displayed isolated characters. Passthrough worked on both. The
0.9.0 software-only tests decoded text but failed to enforce continuous tuple
budgets and field slots. Version 0.9.1 adds checks on actual encoded H.264,
MPEG-2 and YouTube-profile FLV bytes, plus native V210/CDP/VANC checks. The user subsequently reported seeing captions on the Leader SDI receiver
with 0.9.1. This is user-reported hardware evidence; YouTube-service reception
of generated 0.9.1 captions remains pending.
