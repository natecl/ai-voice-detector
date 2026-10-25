# Voice Check: agent knowledge and operating guide

This is the operating guide for another agent taking over this project. “Voice
companion,” “Voice Check,” “widget,” and “pill” refer to this app. It predicts
whether speech resembles human or synthetic audio, locally on a Mac.

Read this guide and `README.md` before operating or modifying the app. These
instructions describe the current implementation, not a planned product.

## 1. Product and current scope

- **Desktop companion:** a floating, draggable macOS pill that listens to system
  playback and displays a separate Human / AI / Waiting badge to its right.
- **Browser app:** upload an audio file or record a microphone sample and analyze
  it. Open `http://127.0.0.1:8765` after starting the backend.
- **CLI:** analyze files with `detector.py`, optionally returning JSON.
- **Default model:** Forensics 0.3B, WavLM + AASIST. Pella is an abandoned experiment
  retained for reference; its pinned checkpoint failed validation.
- **No caller isolation:** system capture combines audio from other apps. Pause
  unrelated music, videos, and notifications during a test.
- **No identity verification:** Human / AI are predictions. The synthetic score
  is not calibrated confidence or a probability that a caller is fraudulent.

## 2. Locate the project and running app

The GitHub repository is `https://github.com/natecl/ai-voice-detector`.
The implementation branch was `Nathan`; check the actual branch and remote
before making changes. Branch state may change after merging.

On the original development Mac:

```text
Project:
/Users/n.chinlue/Documents/Codex/2026-10-23/hey-i-am-thinking-of-making/ai-voice-detector
App bundle:
/Users/n.chinlue/Documents/Codex/2026-10-23/hey-i-am-thinking-of-making/outputs/Voice Check.app
```

For a different checkout, the builder writes to `../outputs/Voice Check.app`.
The bundle embeds the checkout's absolute path and uses that checkout's `.venv`.
It is a local development bundle, not a portable installer. Rebuild if the
checkout moves. Model weights, audio fixtures, REA evidence, and environments
live in ignored directories and are not supplied by a Git clone.

## 3. Start and use the desktop companion

1. Open the existing **Voice Check.app**. Avoid rebuilding merely to launch it.
2. The app appears as a tiny pill, initially near the bottom of the screen or at
   the position saved from the previous session. There is a waveform menu-bar
   icon and no normal Dock icon.
3. Click the pill once to start capturing system audio. It expands to show a
   waveform. macOS may require Screen & System Audio Recording permission.
4. Play clear speech through a call, video, or a known local fixture. Headphones
   work; microphone loopback is unnecessary.
5. Allow at least one complete five-second window plus inference time. The badge
   appears to the right. It can show Starting…, Listening, Checking…, Human, AI,
   Waiting, Access, or Try again.
6. Click the pill again to stop. Escape also stops when the widget has keyboard
   focus. Stopping clears the waveform and verdict badge.
7. Drag the pill to move it. A movement of at least four points is a drag and
   does not toggle capture. The badge follows. The app saves the position on
   release, restores it on launch, and keeps it visible after display changes.
8. Use the menu-bar icon → **Show Voice Check** if the window is hidden, and
   **Quit Voice Check** to quit. Command-Q also quits when the app receives it.

The X and check glyphs within the recording pill are currently parts of the
same stop button; they do not discard or submit separate sessions. The current
pill has no details/upload panel or hover toolbar. Use the browser for uploads,
recordings, scores, and crop details. Do not follow old screenshots showing a
large panel, drag grip, or expand button.

The app starts the backend if it cannot find a ready one at port 8765. On quit,
it terminates only a backend that it started. An independently launched backend
can remain running. Startup can take time while loading/downloading the model.

## 4. Interpret waveform and results

The waveform reflects real system-audio amplitude before normalization. Seven
bars show recent 50 ms RMS measurements, mapped from -60 to -12 dBFS. It updates
separately from inference; it is not a confidence meter or a frequency spectrum.
Silence reduces the bars to minimum height. Missing level events clear them
after 250 ms. Results arrive from five-second speech windows.

| Display | Meaning / next action |
| --- | --- |
| Tiny idle pill, no badge | Capture is off; click to start. |
| Starting… / Listening / Checking… | Capture or analysis is in progress; allow a full window. |
| Human | Latest classified window scored below 0.5 on the synthetic scale. |
| AI | Latest classified window scored at least 0.5 on the synthetic scale. |
| Waiting | Window was too quiet or contained too little detected speech; no verdict. |
| Access | An error occurred; inspect the error message/tooltip and backend logs. Often a macOS capture authorization issue. |
| Try again | A capture/analysis warning occurred; inspect the message before retrying. |

A previous Human / AI badge stays visible while the next window is analyzed.
Quiet or insufficient-speech windows clear that verdict. Overlapping speakers,
noise, compression, unfamiliar synthesis engines, and music can change results.
Do not describe one successful demo or the fixture evaluations as live-call
accuracy. Inference windows may be skipped while another request is busy.

## 5. Use the browser app

From the repository root:

```sh
.venv/bin/python app.py
```

Open `http://127.0.0.1:8765`.

**Upload:** choose a file or drop one on the upload area, then click **Analyze
voice**. **Microphone:** click **Record my voice**, allow the requested microphone
permission, speak, click stop, then **Analyze voice**. Recording stops
automatically near 119 seconds. Use **Remove** to clear the sample and result.

The browser accepts uploads up to 25 MiB and audio up to 120 seconds, decoded by
ffmpeg. WAV, MP3, M4A, FLAC, OGG, and WebM are supported through decoding. A clear
5–15 second speech clip is a useful manual test. File analysis classifies only
the center five seconds; short accepted clips are repeated to fill five seconds.
The result shows the crop, score, and inference time. Do not claim the whole
uploaded recording was classified.

System-audio capture is supplied by the native app. Opening `?widget=1` in an
ordinary browser does not provide the native capture bridge.

## 6. Setup, build, and CLI

Requirements: Python 3.12, `uv`, ffmpeg on PATH, and network access for the first
model/config download. Building the desktop app also needs macOS 13+ and Swift
command-line tools. Node is used for the widget state checks.

```sh
uv venv --python 3.12
uv pip sync --python .venv/bin/python requirements.txt
.venv/bin/python detector.py /absolute/path/to/clip.wav --json
.venv/bin/python scripts/build_widget.py
```

The CLI defaults to CPU. `--device mps` requests the Apple GPU, `--weights PATH`
uses a local safetensors checkpoint, and multiple file arguments share one model
load. The backend uses CPU and the fixed threshold 0.5. Do not tune thresholds
against test fixtures and then report those same fixtures as independent QA.

Pinned detector:
`eliya/forensics_0.3B_base_deepfake_classifier` revision
`cfd11365b02167214dc3b392378809fef6ca3cfa`.
Backend-local checkpoint override:
`work/forensics/checkpoint_epoch_5.safetensors`.
Without it, loading downloads the pinned checkpoint through Hugging Face.
See `THIRD_PARTY.md` for attribution and the model's CC BY-NC 4.0 terms.

## 7. Local API and data handling

The server binds to `127.0.0.1:8765`. It checks Host and Origin, and does not
provide a public remote service or a remote caller API.

```sh
curl --fail http://127.0.0.1:8765/health
curl --fail --request POST \
  --header 'Content-Type: application/octet-stream' \
  --data-binary @/absolute/path/to/clip.wav \
  http://127.0.0.1:8765/analyze
```

- `GET /health`: `{"ready":true,"local":true}` when the model is loaded.
- `POST /analyze`: raw audio bytes, not multipart form data.
- `POST /analyze/live`: same format, with a speech/volume gate before inference.
  Raw RMS below 0.002 or WebRTC VAD speech fraction below 0.30 returns
  `status: "insufficient_speech"` with no prediction.
- Successful classifications contain `status`, `prediction`, `synthetic_score`,
  crop metadata, inference timing, model, and device. Check HTTP status and the
  response `error` field on failures.

Audio analysis runs locally. Temporary backend decoding files are removed when
a request finishes. The capture code registers audio output only; it consumes
and saves no screen images. Initial setup downloads model assets externally.
Fixture scripts download or generate test data and keep it under ignored
`work/`; those saved fixtures are separate from temporary live-analysis files.

## 8. Permission and startup troubleshooting

**Capture denied despite an enabled toggle:** native development builds are
ad-hoc signed. Rebuilding changes the executable's signature and can leave
macOS matching an older code requirement. This has repeatedly occurred on the
original Mac; repeated toggles of the stale entry did not repair it.

1. Quit Voice Check. Check the actual error; confirm the backend is healthy.
2. If signature mismatch is the cause, reset only this app's capture entry:

   ```sh
   tccutil reset ScreenCapture local.natecl.voice-check
   ```

3. Reopen Voice Check and request capture, then have the user enable the fresh
   Voice Check entry under **System Settings → Privacy & Security → Screen &
   System Audio Recording** and choose Quit & Reopen if requested.
4. Test the completed build. Avoid another native rebuild after authorization
   unless it is necessary. Never reset other apps' privacy permissions.

The last drag-feature build compiled and restored position correctly, but capture
was denied during its test. Do not assume that build has since been authorized;
verify the user's current permission state before claiming live capture works.

**Starting forever / cannot reach detector:** check `/health`, run `app.py` in a
terminal for its actual error, and inspect `work/widget-server.log` if the app
launched it. Check the embedded checkout path, `.venv`, model availability,
ffmpeg PATH, and port conflicts. Do not kill unrelated processes on port 8765.

**Build verification reports Finder metadata:** the builder removes signing-
incompatible metadata, but Finder can race it and reapply `com.apple.FinderInfo`
to the output bundle. If that is the reported error, remove only that attribute
from the generated bundle and rerun `codesign --verify --deep --strict` on it.
Do not treat a failed verification as a successful build.

**Waveform moves but Waiting persists:** play isolated, clear speech for more
than five seconds; check the local endpoint and speech gate. A moving waveform
alone does not establish that a valid classification was produced.

## 9. Verification and safe handoff

Run from the repo root after relevant changes:

```sh
.venv/bin/python -m pytest -q
node tests/widget_state_test.cjs
```

The tests cover input/weight validation, endpoint restrictions and cleanup,
silence handling, QA metric calculations, and widget state transitions. They do
not replace a native capture or drag test. For Swift edits, type-check or build;
build only when a new native executable is needed because of permission churn.

Manual desktop acceptance:

1. Launch idle; drag to a different position without starting capture.
2. Quit/relaunch and confirm the position is restored.
3. Once authorized, click to start, play a known human fixture, then a known AI
   fixture. Allow complete windows and inspect both waveform and right badge.
4. Stop playback; confirm the waveform falls and verdict becomes Waiting.
5. Click to stop; confirm idle and no residual badge or audio activity.
6. Stop test playback and capture before handing control back to the user.

Use existing consented/public research fixtures. Fresh ElevenLabs generation
was not performed; the user chose Chatterbox only. Do not claim ElevenLabs QA.

## 10. Source map and evaluation records

| File | Responsibility |
| --- | --- |
| `desktop/main.swift` | AppKit panel, drag tracking, position preferences, menu, backend lifecycle, trusted WKWebView bridge. |
| `desktop/SystemAudioCapture.swift` | ScreenCaptureKit audio, 16 kHz mono buffers, RMS levels, five-second WAVs, local requests, stale-session protection. |
| `ui/index.html` | Browser upload/record UI, pill styles, waveform rendering, right badge, event handling. |
| `app.py` | FastAPI server, ffmpeg decoding, input limits, live speech gate, serialized CPU inference. |
| `detector.py` | Pinned Forensics model, safetensors validation, preprocessing, score direction, CLI. |
| `scripts/build_widget.py` | Local app bundle, embedded checkout path, ad-hoc signing and verification. |
| `tests/` | Automated backend/detector/metrics/widget checks. |
| `vendor/` | Attributed upstream model/reference code; see `THIRD_PARTY.md`. |

Evaluation records: `TEST_RESULTS.md` (initial smoke), `QA_RESULTS.md` (268 public
fixtures and phone-band simulations), `FRESH_CLONE_RESULTS.md` (15 fresh
Chatterbox clones / 10 humans), `WATERMARK_ABLATION_RESULTS.md` (15 matched
pre/post-watermark pairs / 10 humans), and `PELLA_TEST_RESULTS.md` (failed model).
Read their limitations before quoting their results.

Wispr Flow was a visual/interaction reference investigated using REA. Extracted
reference code and evidence remain in ignored `work/rea/`; they are not part of
the shipped source. The app implements an adapted detection workflow and should
not be described as reproducing every Wispr Flow behavior.

For handoff, report the branch/commit, checks actually run, whether the native
app was rebuilt, whether capture is currently authorized/tested, and whether
capture or test audio is still running. Never commit credentials, environments,
model weights, private audio, extracted reference apps, or generated app bundles.
