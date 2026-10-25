# Voice Check on Windows

The Windows companion is a native WPF pill. It captures system playback through
WASAPI loopback and uses the same local Python detector as the Mac app.

## Requirements and first run

Use 64-bit Windows 10/11 with an active output device. The default build targets
x64; an ARM64 publishing option exists but has not been validated with the Python
ML dependencies. Install Python 3.12 (or `uv`), ffmpeg on PATH, and the .NET 8 SDK
for building the widget. A published self-contained widget includes its .NET
runtime, but still needs the repository, Python environment, ffmpeg, and model.

Official downloads: [Python](https://www.python.org/downloads/windows/),
[uv](https://docs.astral.sh/uv/getting-started/installation/),
[.NET 8 SDK](https://dotnet.microsoft.com/download/dotnet/8.0).
One ffmpeg installation option is `winget install --id Gyan.FFmpeg --exact`.
Reopen PowerShell after installing tools so PATH is refreshed.

From your checkout, run in PowerShell:

```powershell
.\scripts\setup_windows.ps1
.\scripts\start_windows.ps1
```

Setup installs Python dependencies into `.venv`. Start builds the Windows app if
needed, then runs it with the repository path. No administrator rights or audio
driver installation are required by the app. If your PowerShell policy blocks
scripts, follow your machine's normal script approval process; the project does
not modify execution policy.

The first click starts the detector if it isn't already running. First use may
download pinned model weights and take several minutes. The pill shows
Starting…; click again to cancel waiting. The backend can finish warming in the
background and is stopped when this widget exits if the widget started it.

To use only the upload/microphone browser app:

```powershell
.\.venv\Scripts\python.exe app.py
```

Open `http://127.0.0.1:8765`. Microphone recording uses the browser's permission
prompt. The pill's loopback capture does not need a microphone or browser access.

## Controls

- Click the pill to start system capture; click again to stop. Space/Enter also
  toggle while the widget has focus; Escape stops.
- Drag the pill to reposition it. A drag does not toggle capture. Position is
  saved in `%LOCALAPPDATA%\VoiceCheck\position.json` and restored next launch.
- The waveform shows actual audio amplitude. Human / AI / Waiting appears in a
  separate badge on the right. Each result describes a five-second window.
- Right-click the tray icon for start/stop, output-device selection, the browser
  app, show/hide, reset position, error details, and quit. Hide stops capture.
  Double-click the tray icon to show the pill. Windows may place it in the hidden
  tray icons area.
- Selecting an output stops capture; click the pill to start again on that
  device. The initial default is Windows' **multimedia** output. Calls routed to
  another headset/communications output need that device selected in the tray.
- The X/check glyphs are part of the same stop target, matching the Mac detector.

Capture combines playback on the selected device, including the browser's own
preview audio; pause unrelated playback. It does not isolate one caller or app.
No microphone loopback, screen capture, virtual cable, or cloud inference is
used. No audio recording is saved by the widget; it posts in-memory WAV windows
to `127.0.0.1:8765/analyze/live`. The Python server removes temporary decode files.
The score is a model prediction, not calibrated confidence or identity proof.

## Silence, devices, and errors

WASAPI may stop delivering packets when nothing is playing. Bars clear after a
short gap; Waiting replaces old verdicts after a one-second packet gap. Partial
windows are reset after longer gaps instead of joining unrelated speech. Silent
packets that do arrive are also tested by the backend's speech gate. Inference
has no queued backlog, and responses from stopped capture sessions are ignored.

Use **Show last status** or hover the pill for error details. Backend output is
in `work/windows-widget-server.log`. Run `app.py` directly to diagnose Python,
model-download, ffmpeg, or port problems. The widget reuses a ready detector and
terminates only a backend process it started. It does not kill unrelated services
on port 8765. Startup fails if a different service answers with an invalid health
contract.

Stop listening before unplugging or reconfiguring an audio device, then select
the replacement and restart. Automatic device switching is not implemented.
Some exclusive-mode or protected playback cannot be captured. macOS privacy
reset commands do not apply on Windows.

If you move the published app away from the checkout, launch it with:

```powershell
& 'C:\path\to\VoiceCheck.exe' --project 'C:\path\to\ai-voice-detector'
```

Keep all files in its publish folder together. To rebuild after source changes:

```powershell
.\scripts\build_windows.ps1
.\scripts\start_windows.ps1
```

## Build and verification

```powershell
dotnet run --project desktop/windows/VoiceCheck.Core.Tests -c Release
dotnet build desktop/windows/VoiceCheck.Windows -c Release
```

The core tests exercise device-rate WAV output, downmix, 16/24/32-bit PCM and
float decoding, non-finite samples, meter levels, chunk boundaries, reset,
local HTTP contracts, error handling, and cancellation. The Windows CI workflow
builds/publishes a self-contained x64 folder, launches a no-capture WPF startup
smoke check on Windows, and uploads the app as an artifact. This
artifact contains the widget, not the Python environment/model/repository. A
separate Windows job runs the actual setup script and Python unit tests without
downloading model weights.

Compilation and core tests can run on macOS with Windows targeting enabled.
They do **not** prove native window behavior, DPI behavior, output-device capture,
or performance on Windows hardware. Before calling a Windows release validated,
run on a Windows PC: drag/relaunch, click start/stop, human and AI fixture playback,
silence, selected headset output, switching devices while stopped, hide/quit,
and backend ownership. These hardware checks remain required.

Local integration check (2026-10-25): the Windows core's 48 kHz stereo PCM →
mono WAV → real local detector path returned Human (0.067) for
`human_6829_0.flac` and AI (0.864) for `chatterbox_1089_0.wav`. These are two
fixtures tested on macOS, not a measurement of Windows live-call accuracy.
