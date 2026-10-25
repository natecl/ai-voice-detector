# Agent entry point

Read [docs/AGENT_GUIDE.md](docs/AGENT_GUIDE.md) for Voice Check's current controls,
architecture, setup, local API, testing, and macOS permission troubleshooting.
Read [README.md](README.md) for quick-start and evaluation commands.

Before editing, check the current branch and working tree. The project repository
is `natecl/ai-voice-detector`; preserve unrelated local work.

On macOS, avoid unnecessary native rebuilds: ad-hoc signatures can invalidate this app's
capture permission. UI-only changes do not require rebuilding the Swift app.
Do not commit model weights, environments, audio fixtures, generated app bundles,
credentials, or extracted reference-app code. Those assets belong in ignored
local directories. See `THIRD_PARTY.md` before redistributing model assets.

## Windows companion

Read [docs/WINDOWS.md](docs/WINDOWS.md) before operating or changing the Windows
version. Its native WPF pill uses WASAPI loopback to capture the selected output
device and sends five-second WAV windows to the same local Python detector.
It supports a reactive waveform, a separate Human/AI/Waiting badge, dragging with
saved position, and tray controls for output selection, the browser app, and quit.

From a Windows checkout, run in PowerShell:

```powershell
.\scripts\setup_windows.ps1
.\scripts\start_windows.ps1
```

Prerequisites: Python 3.12 or uv, ffmpeg on PATH, and the .NET 8 SDK to build.
The self-contained published widget includes .NET but still requires the Python
checkout/environment and model assets. Select the correct headset/output in the
tray; capture combines all playback on that device. Stop before changing devices.
Windows settings are stored in `%LOCALAPPDATA%\VoiceCheck\position.json`.
macOS capture-permission reset commands do not apply to Windows.

Source: `desktop/windows/`. Build: `scripts/build_windows.ps1`. Checks:

```powershell
dotnet run --project desktop/windows/VoiceCheck.Core.Tests -c Release
.\.venv\Scripts\python.exe -m pytest -q
```

The Windows CI workflow builds/publishes x64, checks native WPF startup without
capture, validates the PowerShell scripts, and runs the fresh Python setup and
backend tests. These checks have passed; actual Windows speaker/headset capture,
manual interactions, and mixed-DPI behavior still require hardware acceptance.
Do not report those manual checks as completed without testing them.
