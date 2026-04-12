@echo off
setlocal enabledelayedexpansion
title YouTube Downloader
cls

echo ========================================================
echo  YouTube Downloader - Gestor de Inicio (Windows)
echo ========================================================
echo.

:: 1. Python verification and installation
:: Note: PyQt6 may fail on very recent Python versions (e.g. 3.14) depending on available binaries.
:: Prefer Python 3.11 for a more stable runtime.
set "PYTHON_CMD="

py -3.11 --version >nul 2>&1
if !errorlevel! equ 0 (
    set "PYTHON_CMD=py -3.11"
    echo [OK] Python 3.11 detectado via py launcher.
) else (
    python --version >nul 2>&1
    if !errorlevel! equ 0 (
        python -c "import sys; raise SystemExit(0 if (3,8) <= sys.version_info < (3,14) else 1)" >nul 2>&1
        if !errorlevel! equ 0 (
            set "PYTHON_CMD=python"
            echo [OK] Python compatible detectado en PATH.
        )
    )

    if not defined PYTHON_CMD (
        echo [INFO] No se encontro Python 3.11 ni una version compatible en PATH.
        echo [INFO] Intentando instalar Python 3.11 automaticamente mediante winget...
        where winget >nul 2>&1
        if !errorlevel! neq 0 (
            echo [ERROR] 'winget' no esta disponible en el sistema.
            echo [ACCION] Instala Python 3.11 manualmente desde https://www.python.org/downloads/
            echo [ACCION] Asegurate de marcar la opcion "Add Python to PATH" durante la instalacion.
            pause
            exit /b 1
        )

        winget install --id Python.Python.3.11 --accept-source-agreements --accept-package-agreements
        if !errorlevel! neq 0 (
             echo [ERROR] Fallo la instalacion de Python mediante winget.
             pause
             exit /b 1
        )

        set "PYTHON_CMD=py -3.11"
        !PYTHON_CMD! --version >nul 2>&1
        if !errorlevel! neq 0 (
            echo [WARN] Python fue instalado pero aun no es reconocido en esta terminal.
            echo [ACCION] Cierra esta ventana y vuelve a ejecutar el script.
            pause
            exit /b 1
        )
    )
)

echo [OK] Entorno base de Python listo (!PYTHON_CMD!).
echo.

:: 2. Virtual environment creation (.venv)
set "VENV_DIR=.venv"
if exist "%VENV_DIR%\Scripts\python.exe" (
    "%VENV_DIR%\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info < (3,14) else 1)" >nul 2>&1
    if !errorlevel! neq 0 (
        echo [INFO] Entorno virtual detectado con Python no compatible para PyQt6. Recreando .venv...
        rmdir /s /q "%VENV_DIR%"
    )
)

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [INFO] Creando entorno virtual aislado venv...
    !PYTHON_CMD! -m venv "%VENV_DIR%"
    if !errorlevel! neq 0 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
    echo [OK] Entorno virtual creado exitosamente.
) else (
    echo [OK] Entorno virtual detectado.
)

set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "VENV_PIP=%VENV_DIR%\Scripts\pip.exe"

:: 3. Dependency installation and update
echo.
echo [INFO] Comprobando y actualizando dependencias...
"%VENV_PYTHON%" -m pip install --upgrade pip >nul 2>&1
"%VENV_PIP%" install -r requirements.txt
if !errorlevel! neq 0 (
    echo [ERROR] Hubo un problema al instalar las dependencias de Python.
    pause
    exit /b 1
)
echo [OK] Dependencias al dia.
echo.

:: 4. Application startup
echo [INFO] Iniciando YouTube Downloader...
"%VENV_PYTHON%" -m src.main.youtube_downloader

if !errorlevel! neq 0 (
    echo.
    echo [ERROR] La aplicacion se cerro inesperadamente.
    echo [INFO] Revisa los logs o la salida anterior para mas detalles.
    pause
    exit /b 1
)

endlocal
exit /b 0
