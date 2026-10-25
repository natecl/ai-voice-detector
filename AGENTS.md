# Agent entry point

Read [docs/AGENT_GUIDE.md](docs/AGENT_GUIDE.md) for Voice Check's current controls,
architecture, setup, local API, testing, and macOS permission troubleshooting.
Read [README.md](README.md) for quick-start and evaluation commands.

Before editing, check the current branch and working tree. The project repository
is `natecl/ai-voice-detector`; preserve unrelated local work.

Avoid unnecessary native rebuilds: ad-hoc signatures can invalidate this app's
capture permission. UI-only changes do not require rebuilding the Swift app.
Do not commit model weights, environments, audio fixtures, generated app bundles,
credentials, or extracted reference-app code. Those assets belong in ignored
local directories. See `THIRD_PARTY.md` before redistributing model assets.
