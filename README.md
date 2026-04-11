<div align="center">
  <img src="assets/icon.png" alt="YouTube Downloader Logo" width="128" height="128">
  <h1>YouTube Downloader</h1>

  [![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
  [![Python](https://img.shields.io/badge/Python-3.11-green.svg)](https://www.python.org/downloads/release/python-3110/)
  [![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-lightgrey.svg)](https://www.microsoft.com/windows)
  [![CI](https://github.com/wilkinbarban/youtube-downloader/actions/workflows/ci.yml/badge.svg)](https://github.com/wilkinbarban/youtube-downloader/actions)
  [![Educational](https://img.shields.io/badge/Purpose-Educational-orange.svg)](#educational-disclaimer--aviso-educativo--aviso-educacional)
</div>

---

> **⚠️ EDUCATIONAL DISCLAIMER / AVISO EDUCATIVO / AVISO EDUCACIONAL**
>
> This project is developed **strictly for educational purposes** to demonstrate Python desktop application development with PyQt6, queue management, background workers, and third-party library integration.
>
> The author does **not** encourage or endorse downloading copyrighted content without the explicit permission of the rights holder. Users are solely responsible for ensuring their use of this software complies with YouTube's [Terms of Service](https://www.youtube.com/t/terms), applicable copyright laws, and local regulations. **The author bears no liability for any misuse by third parties.**
>
> ---
> Este proyecto es desarrollado **estrictamente con fines educativos**. El autor no se hace responsable del uso que los usuarios hagan del mismo. Consulte los [Términos de Servicio de YouTube](https://www.youtube.com/t/terms) y la legislación local aplicable antes de descargar cualquier contenido.
>
> ---
> Este projeto é desenvolvido **estritamente para fins educacionais**. O autor não se responsabiliza pelo uso feito pelos usuários. Consulte os [Termos de Serviço do YouTube](https://www.youtube.com/t/terms) e a legislação local aplicável antes de baixar qualquer conteúdo.

---

## Language / Idioma / Idioma

- [Español](#español)
- [English](#english)
- [Português (Brasil)](#português-brasil)

---

## Español

### Descripción
Aplicación de escritorio para Windows creada con Python y PyQt6 para gestionar descargas de YouTube (video, playlist y audio), con cola concurrente, historial, logs y monitor del portapapeles.

### Características
- Descarga de videos individuales, playlists y extracción de audio.
- Hasta 3 descargas simultáneas.
- Monitor automático del portapapeles para detectar enlaces de YouTube.
- Historial de resultados y panel de logs.
- Interfaz multilenguaje: Español, English y Português (Brasil).
- Integración con FFmpeg para mezcla de video y audio.

### Requisitos
- Windows 10/11.
- Python compatible: >=3.8 y <3.14 (recomendado: 3.11).
- Conexión a Internet.
- Winget recomendado para instalación automática de Python/FFmpeg.

### Instalación rápida
### Instalación con un solo comando (PowerShell)

**Opción A — Ya tienes el repositorio clonado o descargado:**
```powershell
Set-ExecutionPolicy -Scope Process Bypass; .\install.ps1
```

**Opción B — Instalación remota directa desde GitHub (sin clonar nada):**
```powershell
Set-ExecutionPolicy -Scope Process Bypass; irm https://raw.githubusercontent.com/wilkinbarban/youtube-downloader/main/install_secure.ps1 | iex
```
> `install_secure.ps1` descarga el repositorio, verifica la integridad del archivo y delega en `install.ps1` localmente. Nunca ejecuta código remoto directamente.

### Instalación rápida (alternativa clásica)
1. Clona o descarga el repositorio.
2. Ejecuta `Iniciar.bat`.
3. El script valida Python, crea `.venv`, instala dependencias y abre la app.

### Dependencia FFmpeg
Si FFmpeg no está instalado, la aplicación puede ofrecer instalarlo automáticamente en Windows usando winget.

---

## English

### Description
Windows desktop application built with Python and PyQt6 to manage YouTube downloads (video, playlists, and audio), including concurrent queueing, history, logs, and clipboard monitoring.

### Features
- Download single videos, playlists, and extract audio.
- Up to 3 concurrent downloads.
- Automatic clipboard monitor for YouTube links.
- Download history and logs panel.
- Multilingual interface: Español, English, and Português (Brasil).
- FFmpeg integration for video/audio merging.

### Requirements
- Windows 10/11.
- Supported Python: >=3.8 and <3.14 (recommended: 3.11).
- Internet connection.
- Winget recommended for automatic Python/FFmpeg installation.

### Quick start
### One-command install (PowerShell)

**Option A — You already have the repository cloned or downloaded:**
```powershell
Set-ExecutionPolicy -Scope Process Bypass; .\install.ps1
```

**Option B — Remote install directly from GitHub (no cloning required):**
```powershell
Set-ExecutionPolicy -Scope Process Bypass; irm https://raw.githubusercontent.com/wilkinbarban/youtube-downloader/main/install_secure.ps1 | iex
```
> `install_secure.ps1` downloads the repository over HTTPS, verifies the archive, and delegates to the local `install.ps1`. It never executes arbitrary remote code directly.

### Quick start (classic alternative)
1. Clone or download the repository.
2. Run `Iniciar.bat`.
3. The script validates Python, creates `.venv`, installs dependencies, and launches the app.

### FFmpeg dependency
If FFmpeg is missing, the app can prompt an automatic installation on Windows through winget.

---

## Português (Brasil)

### Descrição
Aplicativo desktop para Windows, desenvolvido com Python e PyQt6, para gerenciar downloads do YouTube (vídeo, playlists e áudio), com fila concorrente, histórico, logs e monitor da área de transferência.

### Recursos
- Download de vídeos individuais, playlists e extração de áudio.
- Até 3 downloads simultâneos.
- Monitor automático da área de transferência para links do YouTube.
- Histórico de downloads e painel de logs.
- Interface multilíngue: Español, English e Português (Brasil).
- Integração com FFmpeg para mesclagem de vídeo e áudio.

### Requisitos
- Windows 10/11.
- Python suportado: >=3.8 e <3.14 (recomendado: 3.11).
- Conexão com a Internet.
- Winget recomendado para instalação automática de Python/FFmpeg.

### Início rápido
### Instalação com um único comando (PowerShell)

**Opção A — Você já tem o repositório clonado ou baixado:**
```powershell
Set-ExecutionPolicy -Scope Process Bypass; .\install.ps1
```

**Opção B — Instalação remota diretamente do GitHub (sem clonar):**
```powershell
Set-ExecutionPolicy -Scope Process Bypass; irm https://raw.githubusercontent.com/wilkinbarban/youtube-downloader/main/install_secure.ps1 | iex
```
> `install_secure.ps1` baixa o repositório via HTTPS, verifica a integridade do arquivo e delega para o `install.ps1` local. Nunca executa código remoto diretamente.

### Início rápido (alternativa clássica)
1. Clone ou baixe o repositório.
2. Execute `Iniciar.bat`.
3. O script valida o Python, cria o `.venv`, instala as dependências e inicia o aplicativo.

### Dependência FFmpeg
Se o FFmpeg não estiver instalado, o aplicativo pode oferecer instalação automática no Windows via winget.

---

---

## Project structure

| File / Folder | Description |
|---|---|
| `youtube_downloader.py` | Application entry point |
| `app_main_window.py` | Main UI orchestration and download queue |
| `app_core.py` | Domain logic, config, URL utilities |
| `app_workers.py` | Background workers (downloads, playlist extraction, clipboard monitor) |
| `app_dependencies.py` | Dependency checks and auto-installers |
| `app_dialogs.py` | Settings and dependency dialogs |
| `app_i18n.py` | Multilingual string translations (ES / EN / PT-BR) |
| `app_logging.py` | Logging utilities |
| `app_paths.py` | Shared path helpers |
| `Iniciar.bat` | Windows bootstrap: validates Python, creates venv, installs deps, launches app |
| `install.ps1` | PowerShell installer: same flow as Iniciar.bat, scriptable and pipeable |
| `install_secure.ps1` | Secure remote installer: downloads repo from GitHub, verifies, then runs install.ps1 |
| `requirements.txt` | Python dependencies with version policy |
| `assets/` | Icons and visual resources |
| `.github/workflows/ci.yml` | CI pipeline (syntax check, Python version guard) |

---

## Educational Disclaimer / Aviso Educativo / Aviso Educacional

This software is provided **for educational purposes only**. It demonstrates:
- PyQt6 desktop application architecture
- Background worker threads with QThread
- Queue-based concurrent download management
- Clipboard monitoring
- Multilingual UI (i18n)
- Automated dependency resolution on Windows

**The author (wilkinbarban) is not responsible for how users choose to use this software.** Downloading copyrighted content without authorization may violate YouTube's [Terms of Service](https://www.youtube.com/t/terms) and applicable copyright laws in your country. Use responsibly.

---

## License

This project is licensed under the **GNU General Public License v3.0**.

You are free to run, study, share, and modify this software under the conditions of the GPL-3.0. Any derivative works must also be distributed under the same license with source code available.

See [LICENSE](LICENSE) for the full license text.

```
YouTube Downloader  Copyright (C) 2026  wilkinbarban
This program comes with ABSOLUTELY NO WARRANTY.
This is free software, and you are welcome to redistribute it
under certain conditions; see LICENSE for details.
```
