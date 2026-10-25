param([ValidateSet('win-x64', 'win-arm64')][string]$Runtime = 'win-x64')
$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $PSScriptRoot
if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) { throw 'Install the .NET 8 SDK from dotnet.microsoft.com, then reopen PowerShell.' }
$Project = Join-Path $Repo 'desktop\windows\VoiceCheck.Windows\VoiceCheck.Windows.csproj'
$Destination = Join-Path $Repo "work\windows-$Runtime"
& dotnet publish $Project -c Release -r $Runtime --self-contained true -o $Destination --nologo
if ($LASTEXITCODE -ne 0) { throw 'Windows build failed.' }
Write-Host "Built $Destination\VoiceCheck.exe"
