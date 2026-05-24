@powershell -NoProfile -ExecutionPolicy Bypass -Command "$ScriptRoot = '%~dp0'; Invoke-Expression ((Get-Content '%~f0' -Encoding utf8 | Select-Object -Skip 1) -join [Environment]::NewLine)" & exit /b
$Version = "1.3.0"

# 1. Host settings
$Host.UI.RawUI.WindowTitle = "YouTube Downloader - Inicializando Entorno"
Clear-Host

Write-Host ""
Write-Host "  *** Y O U T U B E   D O W N L O A D E R  ***" -ForegroundColor Magenta
Write-Host "  ========================================" -ForegroundColor DarkCyan
Write-Host "   Gestor de Arranque Autonomo - Version $Version" -ForegroundColor Gray
Write-Host "  ========================================" -ForegroundColor DarkCyan
Write-Host ""

# Status indicator helper
function Show-Step {
    param (
        [string]$Message
    )
    Write-Host "  >> $Message..." -ForegroundColor Gray
}

# Error presentation helper
function Show-Error {
    param (
        [string]$Title,
        [string]$Detail,
        [string]$Action
    )
    Write-Host ""
    Write-Host "  [ERROR] $Title" -ForegroundColor Red
    Write-Host "  --------------------------------------------------------" -ForegroundColor Red
    Write-Host "   Detalle : $Detail" -ForegroundColor Yellow
    Write-Host "   Accion  : $Action" -ForegroundColor Cyan
    Write-Host "  --------------------------------------------------------" -ForegroundColor Red
    Write-Host ""
    Read-Host "  Presione Enter para salir..."
    exit 1
}

# Lightweight execution runner with progress spinner and real-time package feedback
function Run-WithProgress {
    param (
        [string]$FileName,
        [string]$Arguments,
        [string]$Message
    )
    $pinfo = New-Object System.Diagnostics.ProcessStartInfo
    $pinfo.FileName = $FileName
    $pinfo.Arguments = $Arguments
    $pinfo.RedirectStandardOutput = $true
    $pinfo.RedirectStandardError = $true
    $pinfo.UseShellExecute = $false
    $pinfo.CreateNoWindow = $true
    
    $p = New-Object System.Diagnostics.Process
    $p.StartInfo = $pinfo
    
    $stdoutList = New-Object System.Collections.Generic.List[string]
    $stderrList = New-Object System.Collections.Generic.List[string]
    
    # Register events for non-blocking stream capture
    $p.EnableRaisingEvents = $true
    
    $outEvent = Register-ObjectEvent -InputObject $p -EventName "OutputDataReceived" -Action {
        if ($EventArgs.Data) {
            $Event.MessageData.Add($EventArgs.Data)
            $script:LastRawLine = $EventArgs.Data
        }
    } -MessageData $stdoutList
    
    $errEvent = Register-ObjectEvent -InputObject $p -EventName "ErrorDataReceived" -Action {
        if ($EventArgs.Data) {
            $Event.MessageData.Add($EventArgs.Data)
        }
    } -MessageData $stderrList
    
    try {
        $script:LastRawLine = ""
        $p.Start() | Out-Null
        $p.BeginOutputReadLine()
        $p.BeginErrorReadLine()
    } catch {
        return @{ Success = $false; Error = $_.Exception.Message }
    }
    
    $spinner = @('|', '/', '-', '\')
    $i = 0
    while (-not $p.HasExited) {
        $displayMessage = $Message
        $lastLine = $script:LastRawLine
        if ($lastLine) {
            if ($lastLine -match 'Downloading\s+([a-zA-Z0-9_\-\.]+)') {
                $displayMessage = "Descargando $($Matches[1])"
            } elseif ($lastLine -match 'Installing collected packages:\s*(.*)') {
                $displayMessage = "Instalando paquetes"
            } elseif ($lastLine -match 'Requirement already satisfied:\s*([a-zA-Z0-9_\-\.\:\(\)\ ]+)') {
                $matched = $Matches[1]
                if ($matched -match '^([a-zA-Z0-9_\-]+)') {
                    $displayMessage = "Verificando $($Matches[1])"
                }
            }
        }
        
        # Limit message length to fit beautifully in standard terminal
        if ($displayMessage.Length -gt 50) {
            $displayMessage = $displayMessage.Substring(0, 47) + "..."
        }
        
        Write-Host -NoNewline "`r  $($spinner[$i]) $displayMessage..." -ForegroundColor Cyan
        Start-Sleep -Milliseconds 100
        $i = ($i + 1) % $spinner.Count
    }
    
    Unregister-Event -SourceIdentifier $outEvent.Name -ErrorAction SilentlyContinue
    Unregister-Event -SourceIdentifier $errEvent.Name -ErrorAction SilentlyContinue
    
    $stdout = $stdoutList -join "`n"
    $stderr = $stderrList -join "`n"
    $exitCode = $p.ExitCode
    
    Write-Host -NoNewline "`r                                                                              `r"
    
    if ($exitCode -eq 0) {
        Write-Host "  [OK] $Message [Completado]" -ForegroundColor Green
        return @{ Success = $true; Stdout = $stdout }
    } else {
        Write-Host "  [FAIL] $Message [Fallo]" -ForegroundColor Red
        return @{ Success = $false; Stdout = $stdout; Stderr = $stderr; ExitCode = $exitCode }
    }
}

# --- Step 1: Detect Python Environment ---
Show-Step "Verificando entorno de Python"

$pythonCmd = $null
$launchers = @("py -3.11", "py -3.12", "py -3.10", "py -3.9", "py -3.8", "py -3.13", "py -3.14")
foreach ($launcher in $launchers) {
    try {
        $parts = $launcher -split " "
        $cmd = $parts[0]
        $arg = $parts[1]
        $res = & $cmd $arg --version 2>&1
        if ($lastExitCode -eq 0 -and $res -match 'Python\s+([0-9\.]+)') {
            $pythonCmd = $launcher
            break
        }
    } catch {}
}

if (-not $pythonCmd) {
    try {
        $res = & python --version 2>&1
        if ($lastExitCode -eq 0 -and $res -match 'Python\s+([0-9\.]+)') {
            $ver = [version]$Matches[1]
            if ($ver -ge [version]"3.8" -and $ver -lt [version]"3.15") {
                $pythonCmd = "python"
            }
        }
    } catch {}
}

# If Python not found, attempt auto-install using winget
if (-not $pythonCmd) {
    Write-Host "  [!] Python compatible (3.8 a 3.14) no detectado en el sistema." -ForegroundColor Yellow
    
    # Check winget availability
    $wingetCheck = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $wingetCheck) {
        Show-Error "Python No Encontrado" "No se encontro Python ni el instalador winget en el sistema." "Instale manualmente Python 3.11 desde https://www.python.org/downloads/ (marcando 'Add Python to PATH')."
    }
    
    # Run winget installer
    Write-Host "  [INFO] Iniciando instalacion automatica de Python 3.11..." -ForegroundColor Cyan
    $installRes = Run-WithProgress "winget" "install --id Python.Python.3.11 --accept-source-agreements --accept-package-agreements" "Instalando Python 3.11"
    
    if (-not $installRes.Success) {
        Show-Error "Instalacion de Python Fallida" "Fallo al instalar Python 3.11 mediante winget." "Por favor, realice la instalacion manual desde el sitio web de Python."
    }
    
    # Retry detection
    Write-Host "  [OK] Instalacion completada. Verificando nuevamente..." -ForegroundColor Green
    foreach ($launcher in $launchers) {
        try {
            $parts = $launcher -split " "
            $cmd = $parts[0]
            $arg = $parts[1]
            $res = & $cmd $arg --version 2>&1
            if ($lastExitCode -eq 0 -and $res -match 'Python\s+([0-9\.]+)') {
                $pythonCmd = $launcher
                break
            }
        } catch {}
    }
    
    if (-not $pythonCmd) {
        Show-Error "Reinicio de Consola Requerido" "Python fue instalado correctamente pero la terminal actual aun no reconoce el comando." "Cierre todas las ventanas de consola abiertas y vuelva a ejecutar Iniciar.bat."
    }
}

Write-Host "  [OK] Python base detectado ($pythonCmd)" -ForegroundColor Green

# --- Step 2: Virtual Environment Setup ---
$venvDir = ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$venvPip = Join-Path $venvDir "Scripts\pip.exe"
$recreateVenv = $false

if (Test-Path $venvPython) {
    try {
        $res = & $venvPython --version 2>&1
        if ($res -match 'Python\s+([0-9\.]+)') {
            $ver = [version]$Matches[1]
            if ($ver -lt [version]"3.8" -or $ver -ge [version]"3.15") {
                $recreateVenv = $true
            }
        } else {
            $recreateVenv = $true
        }
    } catch {
        $recreateVenv = $true
    }
}

if ($recreateVenv) {
    Write-Host "  [!] Entorno virtual incompatible detectado. Recreando .venv..." -ForegroundColor Yellow
    Remove-Item -Path $venvDir -Recurse -Force -ErrorAction SilentlyContinue
}

if (-not (Test-Path $venvPython)) {
    # Extract command for venv execution
    $parts = $pythonCmd -split " "
    $cmd = $parts[0]
    $venvArgs = if ($parts.Length -gt 1) { "$($parts[1]) -m venv $venvDir" } else { "-m venv $venvDir" }
    
    $venvRes = Run-WithProgress $cmd $venvArgs "Creando entorno virtual (.venv)"
    if (-not $venvRes.Success) {
        Show-Error "Error de Entorno Virtual" "No se pudo crear la carpeta .venv." "Verifique permisos de escritura en la carpeta del proyecto o intente ejecutar: python -m venv .venv"
    }
} else {
    Write-Host "  [OK] Entorno virtual detectado (.venv)" -ForegroundColor Green
}

# --- Step 3: Dependencies Check & Installation ---
Show-Step "Comprobando dependencias del sistema"

# Disable global pip installation to enforce isolated venv
$env:PIP_USER = "no"

# Upgrade pip quietly
$pipUpgrade = Run-WithProgress $venvPython "-m pip install --no-input --upgrade pip" "Actualizando instalador pip"

# Check dependencies from requirements.txt
$ReqPath = Join-Path $ScriptRoot "requirements.txt"
if (Test-Path $ReqPath) {
    $depsRes = Run-WithProgress $venvPip "install --no-input -r `"$ReqPath`"" "Instalando dependencias de Python"
    if (-not $depsRes.Success) {
        $logFile = Join-Path $venvDir "install.log"
        $depsRes.Stderr | Out-File -FilePath $logFile -Encoding utf8
        Show-Error "Error en Dependencias" "Fallo al instalar paquetes de requirements.txt." "Consulte el archivo de log en: $logFile`nIntente ejecutar manualmente: .venv\Scripts\pip.exe install -r requirements.txt"
    }
} else {
    Write-Host "  [!] requirements.txt no encontrado. Omitiendo instalacion de dependencias." -ForegroundColor Yellow
}

# --- Step 4: Run Application ---
Write-Host "  >>> Iniciando YouTube Downloader..." -ForegroundColor Magenta
Write-Host ""

try {
    # Launch in background and wait, showing direct stdout/stderr stream from app
    $proc = Start-Process -FilePath $venvPython -ArgumentList "-m src.main.youtube_downloader" -NoNewWindow -PassThru -Wait
    $exitCode = $proc.ExitCode
    if ($exitCode -ne 0) {
        Show-Error "Ejecucion Fallida" "La aplicacion finalizo con un codigo de error inesperado ($exitCode)." "Consulte la salida anterior o los archivos de log de la aplicacion para mas detalles."
    }
} catch {
    Show-Error "Fallo Critico al Iniciar" $_.Exception.Message "Compruebe que el entorno virtual no este danado e intente re-ejecutar el script."
}
