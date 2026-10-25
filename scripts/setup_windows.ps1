# Run in PowerShell from a clone of this repository. Installs only into .venv.
$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Repo
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    throw 'ffmpeg is missing from PATH. Install it (e.g. winget install --id Gyan.FFmpeg --exact), reopen PowerShell, and retry.'
}
if (Get-Command uv -ErrorAction SilentlyContinue) {
    & uv venv --python 3.12 .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create Python 3.12 environment.' }
    & uv pip sync --python .venv\Scripts\python.exe requirements.txt
} else {
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw 'Install Python 3.12 (python.org) or uv, then retry.' }
    & py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 is required.' }
    & .\.venv\Scripts\python.exe -m pip install -r requirements.txt
}
if ($LASTEXITCODE -ne 0) { throw 'Python dependencies could not be installed. Review the installer error above.' }
Write-Host 'Python setup complete. Run .\scripts\start_windows.ps1 for the pill.'
Write-Host 'Or run .\.venv\Scripts\python.exe app.py and open http://127.0.0.1:8765 for uploads and microphone recording.'
