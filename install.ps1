#Requires -Version 5.1
<#
.SYNOPSIS
    YouTube Downloader - One-command installer and launcher for Windows.

.DESCRIPTION
    Validates the Python runtime (requires >=3.8, <3.14; prefers 3.11),
    creates an isolated virtual environment, installs all dependencies,
    and launches the application.

    This script is intended for EDUCATIONAL USE ONLY. The user is solely
    responsible for complying with YouTube's Terms of Service and applicable
    copyright laws.

.EXAMPLE
    # Run from PowerShell (no clone needed if you use the remote variant):
    .\install.ps1

    # Or directly from GitHub (see install_secure.ps1 for the safe remote variant):
    irm https://raw.githubusercontent.com/wilkinbarban/youtube-downloader/main/install_secure.ps1 | iex

.NOTES
    Platform : Windows 10/11
    License  : GNU General Public License v3.0
    Author   : wilkinbarban
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Write-Step  { param([string]$Msg) Write-Host "[....] $Msg" -ForegroundColor Cyan }
function Write-Ok    { param([string]$Msg) Write-Host "[ OK ] $Msg" -ForegroundColor Green }
function Write-Warn  { param([string]$Msg) Write-Host "[WARN] $Msg" -ForegroundColor Yellow }
function Write-Fail  { param([string]$Msg) Write-Host "[FAIL] $Msg" -ForegroundColor Red }
function Write-Info  { param([string]$Msg) Write-Host "[INFO] $Msg" -ForegroundColor Gray }

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "  YouTube Downloader - Installer / Launcher (Windows)" -ForegroundColor Cyan
Write-Host "  Educational project - GPL-3.0 License" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------------
# 1. Locate a compatible Python runtime (>=3.8, <3.14; prefer 3.11)
# ---------------------------------------------------------------------------
Write-Step "Locating compatible Python runtime..."

$PythonCmd = $null

# Try py -3.11 first (Windows Python Launcher)
try {
    $null = & py -3.11 --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        $PythonCmd = @('py', '-3.11')
        Write-Ok "Python 3.11 found via py launcher."
    }
} catch { <# not available #> }

# Fallback: python in PATH if version is compatible
if (-not $PythonCmd) {
    try {
        $null = & python --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $compatible = & python -c "import sys; raise SystemExit(0 if (3,8) <= sys.version_info < (3,14) else 1)" 2>&1
            if ($LASTEXITCODE -eq 0) {
                $PythonCmd = @('python')
                Write-Ok "Compatible Python found in PATH."
            } else {
                Write-Warn "Python in PATH is outside the supported range (>=3.8, <3.14)."
            }
        }
    } catch { <# not available #> }
}

# Last resort: install Python 3.11 via winget
if (-not $PythonCmd) {
    Write-Info "No compatible Python found. Attempting automatic install via winget..."
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Fail "winget is not available. Install Python 3.11 manually from https://www.python.org/downloads/"
        Write-Fail "Make sure to check 'Add Python to PATH' during installation."
        exit 1
    }
    & winget install --id Python.Python.3.11 --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "winget installation failed. Please install Python 3.11 manually."
        exit 1
    }
    # Refresh PATH for the current session
    $env:PATH = [System.Environment]::GetEnvironmentVariable('PATH', 'Machine') + ';' +
                [System.Environment]::GetEnvironmentVariable('PATH', 'User')
    try {
        $null = & py -3.11 --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $PythonCmd = @('py', '-3.11')
            Write-Ok "Python 3.11 installed and ready."
        }
    } catch { }
    if (-not $PythonCmd) {
        Write-Warn "Python was installed but is not yet visible in this session."
        Write-Info "Please close this window and run the script again."
        exit 1
    }
}

# ---------------------------------------------------------------------------
# 2. Create or validate virtual environment
# ---------------------------------------------------------------------------
Write-Host ""
Write-Step "Setting up virtual environment (.venv)..."

$VenvDir    = Join-Path $PSScriptRoot '.venv'
$VenvPython = Join-Path $VenvDir 'Scripts\python.exe'
$VenvPip    = Join-Path $VenvDir 'Scripts\pip.exe'

# Recreate venv if it was built with an incompatible Python (e.g. 3.14)
if (Test-Path $VenvPython) {
    $incompatible = & $VenvPython -c "import sys; raise SystemExit(0 if sys.version_info < (3,14) else 1)" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "Existing .venv uses an incompatible Python version. Recreating..."
        Remove-Item -Recurse -Force $VenvDir
    }
}

if (-not (Test-Path $VenvPython)) {
    Write-Info "Creating isolated virtual environment..."
    & @PythonCmd -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Failed to create virtual environment."
        exit 1
    }
    Write-Ok "Virtual environment created."
} else {
    Write-Ok "Virtual environment already exists."
}

# ---------------------------------------------------------------------------
# 3. Install / update dependencies
# ---------------------------------------------------------------------------
Write-Host ""
Write-Step "Installing dependencies..."

& $VenvPython -m pip install --upgrade pip --quiet
& $VenvPip install -r (Join-Path $PSScriptRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Dependency installation failed. Check the output above for details."
    exit 1
}
Write-Ok "All dependencies are up to date."

# ---------------------------------------------------------------------------
# 4. Launch application
# ---------------------------------------------------------------------------
Write-Host ""
Write-Ok "Launching YouTube Downloader..."
Write-Host ""

& $VenvPython (Join-Path $PSScriptRoot 'youtube_downloader.py')

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Fail "Application exited unexpectedly (exit code $LASTEXITCODE)."
    Write-Info "Check the Logs tab or the output above for details."
    exit $LASTEXITCODE
}
