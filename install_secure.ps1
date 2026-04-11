#Requires -Version 5.1
<#
.SYNOPSIS
    YouTube Downloader - Secure remote installer for Windows.

.DESCRIPTION
    Downloads the repository from GitHub, verifies integrity, and runs
    install.ps1 to set up and launch YouTube Downloader.

    Designed to be run with a single PowerShell command:

        irm https://raw.githubusercontent.com/wilkinbarban/youtube-downloader/main/install_secure.ps1 | iex

    Security measures applied:
    - Downloads only over HTTPS (TLS 1.2+).
    - Verifies the downloaded archive is non-empty before extracting.
    - Extracts to a predictable, user-owned directory.
    - Never elevates to Administrator or modifies system-wide settings.
    - Does not execute arbitrary remote code directly — clones to disk first,
      then runs the local install.ps1.

    This script is intended for EDUCATIONAL USE ONLY. The user is solely
    responsible for complying with YouTube's Terms of Service and applicable
    copyright laws.

.PARAMETER InstallDir
    Target directory for the repository clone.
    Defaults to: $HOME\Desktop\youtube-downloader

.EXAMPLE
    # One-liner from any PowerShell window (no Git required):
    irm https://raw.githubusercontent.com/wilkinbarban/youtube-downloader/main/install_secure.ps1 | iex

    # With a custom install directory:
    $env:YTD_INSTALL_DIR = "C:\Tools\youtube-downloader"
    irm https://raw.githubusercontent.com/wilkinbarban/youtube-downloader/main/install_secure.ps1 | iex

.NOTES
    Platform : Windows 10/11
    License  : GNU General Public License v3.0
    Author   : wilkinbarban
    Requires : PowerShell 5.1+, Internet connection, HTTPS access to GitHub
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# Enforce TLS 1.2 minimum for all web requests
# ---------------------------------------------------------------------------
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Write-Step { param([string]$Msg) Write-Host "[....] $Msg" -ForegroundColor Cyan }
function Write-Ok   { param([string]$Msg) Write-Host "[ OK ] $Msg" -ForegroundColor Green }
function Write-Warn { param([string]$Msg) Write-Host "[WARN] $Msg" -ForegroundColor Yellow }
function Write-Fail { param([string]$Msg) Write-Host "[FAIL] $Msg" -ForegroundColor Red }
function Write-Info { param([string]$Msg) Write-Host "[INFO] $Msg" -ForegroundColor Gray }

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "  YouTube Downloader - Secure Remote Installer" -ForegroundColor Cyan
Write-Host "  Educational project - GPL-3.0 License" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
$RepoOwner   = 'wilkinbarban'
$RepoName    = 'youtube-downloader'
$Branch      = 'main'
$ArchiveUrl  = "https://github.com/$RepoOwner/$RepoName/archive/refs/heads/$Branch.zip"
$DesktopDir  = [Environment]::GetFolderPath('Desktop')
if ([string]::IsNullOrWhiteSpace($DesktopDir)) {
    $DesktopDir = Join-Path $HOME 'Desktop'
}
$InstallDir  = if ($env:YTD_INSTALL_DIR) { $env:YTD_INSTALL_DIR } else { Join-Path $DesktopDir $RepoName }
$TempZip     = Join-Path $env:TEMP "$RepoName-$Branch.zip"
$TempExtract = Join-Path $env:TEMP "$RepoName-extract-$(Get-Random)"

# ---------------------------------------------------------------------------
# 1. Download repository archive over HTTPS
# ---------------------------------------------------------------------------
Write-Step "Downloading repository from GitHub..."
Write-Info "Source : $ArchiveUrl"
Write-Info "Target : $InstallDir"
Write-Host ""

try {
    Invoke-WebRequest -Uri $ArchiveUrl -OutFile $TempZip -UseBasicParsing
} catch {
    Write-Fail "Download failed: $_"
    Write-Info "Check your internet connection and that github.com is reachable."
    exit 1
}

# Verify the downloaded file is non-empty (basic integrity check)
$zipSize = (Get-Item $TempZip).Length
if ($zipSize -lt 1024) {
    Write-Fail "Downloaded archive appears invalid (size: $zipSize bytes). Aborting."
    Remove-Item -Force $TempZip -ErrorAction SilentlyContinue
    exit 1
}
Write-Ok "Archive downloaded ($([math]::Round($zipSize/1KB, 1)) KB)."

# ---------------------------------------------------------------------------
# 2. Extract archive to a temporary directory
# ---------------------------------------------------------------------------
Write-Step "Extracting archive..."
$null = New-Item -ItemType Directory -Path $TempExtract -Force
Expand-Archive -Path $TempZip -DestinationPath $TempExtract -Force
Remove-Item -Force $TempZip -ErrorAction SilentlyContinue

# GitHub archives extract as RepoName-BranchName/
$ExtractedRoot = Join-Path $TempExtract "$RepoName-$Branch"
if (-not (Test-Path $ExtractedRoot)) {
    Write-Fail "Expected folder '$ExtractedRoot' not found after extraction."
    Remove-Item -Recurse -Force $TempExtract -ErrorAction SilentlyContinue
    exit 1
}
Write-Ok "Extracted successfully."

# ---------------------------------------------------------------------------
# 3. Move to final install directory
# ---------------------------------------------------------------------------
Write-Step "Installing to: $InstallDir"

if (Test-Path $InstallDir) {
    Write-Warn "Directory already exists. Updating in-place (existing .venv preserved)."
    # Copy all files except .venv so the environment is not overwritten
    Get-ChildItem -Path $ExtractedRoot | Where-Object { $_.Name -ne '.venv' } | ForEach-Object {
        $dest = Join-Path $InstallDir $_.Name
        Copy-Item -Path $_.FullName -Destination $dest -Recurse -Force
    }
} else {
    Move-Item -Path $ExtractedRoot -Destination $InstallDir
}

Remove-Item -Recurse -Force $TempExtract -ErrorAction SilentlyContinue
Write-Ok "Files installed."

# ---------------------------------------------------------------------------
# 4. Delegate to local install.ps1
# ---------------------------------------------------------------------------
Write-Host ""
Write-Step "Running installer from local copy..."
$LocalInstaller = Join-Path $InstallDir 'install.ps1'

if (-not (Test-Path $LocalInstaller)) {
    Write-Fail "install.ps1 not found in $InstallDir. The repository may be incomplete."
    exit 1
}

# Run install.ps1 in the install directory context
Set-Location $InstallDir
& $LocalInstaller
exit $LASTEXITCODE
