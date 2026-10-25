param([ValidateSet('win-x64', 'win-arm64')][string]$Runtime = 'win-x64')
$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath (Join-Path $Repo '.venv\Scripts\python.exe'))) { throw 'Run scripts\setup_windows.ps1 first.' }
$Executable = Join-Path $Repo "work\windows-$Runtime\VoiceCheck.exe"
if (-not (Test-Path -LiteralPath $Executable)) {
    & (Join-Path $PSScriptRoot 'build_windows.ps1') -Runtime $Runtime
}
# Use call operator for argument boundaries, including repository paths containing spaces.
& $Executable --project $Repo
