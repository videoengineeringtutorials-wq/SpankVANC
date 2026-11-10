For EN530 serial captions without video playout, select **NULL · EN530 serial
only** as the output type and enter the EN530 serial port above. NULL runs
Whisper from the selected source audio without a video/audio destination or
video encoder. The source is still required; SDI capture still needs its input
device and mode. NULL can also be enabled alongside normal video outputs;
they share one recognition worker and serial connection. Serial sends English
captions; video caption format and Spanish CC2 settings do not apply to NULL.

## Faster Whisper and EN530 serial output

The recaptioning panel now selects **OpenAI Whisper** (the saved-route default)
or **Faster Whisper · overlap dedup**. Faster Whisper uses routed mono 16 kHz
program audio with a four-second rolling window, a two-second hop, beam size 3,
word timestamps and a 0.35-second stability margin. Words are deduplicated by
absolute audio time, with text overlap matching when timestamps are missing.
Dropped audio resets the rolling context without compressing the audio timeline.
This follows the supplied audioWhisper EN530 dedup approach. Speed and recognition
quality depend on the model, hardware and program material; no comparative
benchmark or physical encoder validation has been performed for this integration.

Install optional dependencies in the Python selected by `whisper_python_path`
(or `SPANKVANC_WHISPER_PYTHON`), then refresh capabilities:

```powershell
& "C:\path\to\speech\python.exe" -m pip install faster-whisper==1.2.1 ctranslate2==4.6.0 pyserial==3.5
```

The 0.15.0 guided installer provisions both OpenAI Whisper and Faster Whisper,
plus pyserial. Existing installations can run Finish Setup to install these
packages in their managed speech Python. Faster Whisper requires
its own CTranslate2 model download/cache; existing OpenAI `.pt` weights cannot be
reused. The configured model cache directory is passed to either backend.
Choose `auto` compute initially, `int8` for CPU or `float16` for compatible CUDA
hardware. CTranslate2 GPU support is independent of the existing Torch CUDA
installation. Model loading and serial opening must succeed before capture starts.

Enter an optional **EN530 serial port**, for example `COM6` or `/dev/ttyUSB0`.
Leave it blank to disable. During a running recaption route, recognized CC1 text
is also sent once to that port, independent of the number of recaption outputs.
This is a serial mirror; at least one enabled output must use recaptioning.
Serial settings are fixed at **1200 baud, seven data bits, odd parity, one stop
bit**. Commands are `01 20` + up to 32 printable ASCII characters + `0D`.
Punctuation is transliterated before wrapping. An `E1` response sends `01 32 0D`
and reads the recovery response without resending that caption. The bounded
serial queue prevents blocking recognition; serial errors or sustained backlog
fail the worker and stop the route visibly. Serial output carries English/source
CC1 text only; Spanish CC2 remains on the existing media output path.

# Optional Spanish CC2 translation

On each output, select **audioWhisper · replace** and enable
**Add Spanish translation on CC2**. The checkbox defaults off. Use **608** or
**608 + 708**; enabling CC2 while 708-only is selected changes the format to both.
Choosing 708-only or Pass/Strip disables the CC2 option for that output.
Whisper language must be **en** for this English-to-Spanish model.

English remains on CEA-608 CC1. Translated Spanish uses **CC2 on field 1**,
including ñ, accented vowels, ¿ and ¡. Native 708 Service 1 remains English;
this option does not create a Spanish 708 Service 2. Other outputs keep their
independent caption policy. Select CC2 on the receiving analyzer/player.

In the 0.14.0 Windows setup, select **Install local English → Spanish translation**,
then rebuild the local engine
with current build support. Preflight checks for both. Model paths default to
`translation/python` and `translation/model` beside the runtime directory; the
model directory contains source.spm, target.spm and the converted ct2 model.
`SPANKVANC_TRANSLATION_HOME` overrides that folder. The translator loads before
capture starts. Core application and Whisper dependencies remain separate.

CC1 and CC2 share the 608 field-1 transmission capacity. The selected output
uses an append-only phrase-atomic journal; unselected outputs retain the original
English journal. Spanish is admitted only within a four-second estimated total
backlog; English has a ten-second bound. Estimates conservatively assume 25 pairs
per second. Overload skips whole phrases and is visible in the Dashboard caption
skip count/backlog. Queued translations retain their original route sink, which
closes at route end, so late results cannot enter a later route. Silence clears
both services. Program A/V is not delayed. Translation errors remain possible.
Manual Dashboard test text is never sent to CC2.

Verification: independent CCExtractor decoding of H.264 and MPEG-2 608/both,
Spanish basic/special/extended glyphs, English CC1/708 isolation, unselected
English-only and stripped outputs, with300 frames retained per output.
A synthetic file route on the Windows workstation exercised actual Whisper,
OPUS translation and the locally built engine, with three translations admitted
and no skipped phrases. Physical CC2 reception and sustained program throughput
still require receiver/live testing.

---

# Generated 608 / native 708 output — 0.13.0

On each desired output, choose **audioWhisper · replace** under Captions, then
choose **Output caption format**:

- **608:** existing CC1 two-row roll-up captions.
- **708:** native Service 1 with a visible two-row roll-up window.
- **608 + 708:** both services carry the same paced text together.

Select formats independently on SDI, UDP, SRT, file, RTMP or YouTube outputs.
Caption format is independent of SCTE policy. SDI uses the existing DeckLink
V210 → CDP/VANC path; H.264 and MPEG-2 carry the caption tuples in A/53 data.
The matching locally rebuilt engine is required for 708 or combined generation;
preflight blocks older engines. Saved replacement routes without a format keep
608; saved passthrough routes keep both source caption types.

The native 708 encoder consumes the app's paced generated CC1 journal to build
real DTVCC packets and Service 1 commands. It initializes and refreshes window 0,
uses bottom-centred two-row roll-up, suppresses duplicated 608 controls, preserves
32-column word wrapping, and clears on the worker's silence timeout. Both formats
therefore share text normalization and pacing. The initial encoder uses the
existing transliterated basic character set, one service and fixed styling;
Unicode, multiple generated services and arbitrary input 608-to-708 conversion
are outside this version. Input capture and monitoring are unchanged.

With **Pass through**, the format selector keeps only the requested types already
present in the source; it does not generate missing captions or convert source
608 into native 708. **608 + 708** preserves the existing source tuples. **Strip**
removes captions and hides the format selector.

Generated SDI CDPs announce the actual selected services: service number 0 for
608 compatibility and Service 1 for native 708, with matching start/complete
flags and language metadata. This follows [SMPTE ST 334-2](https://pub.smpte.org/latest/st334-2/st0334-2-2015.pdf).
Digital packets use sequence counts, complete service blocks, valid start and
continuation tuples, and frame-rate-specific caption budgets.

Verification includes independent CCExtractor native-708 text decoding from
actual H.264 and MPEG-2 output in 708-only and combined modes, 608 text decoding,
full frame counts, packet sequencing and output isolation. Native Windows tests
cover 24 format/rate combinations through the real filter, V210 packet carriage,
CDP service parsing, VANC checksums, partial journal appends and source-frame
isolation. The user subsequently confirmed the new output worked on their Leader monitor.
This establishes user-reported physical reception, with format/rate and separate
service checks unspecified. Select CC1 and Service 1 independently on the
analyzer when checking both mode.

---

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
