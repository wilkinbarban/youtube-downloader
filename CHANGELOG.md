# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `install.ps1`: PowerShell one-command installer and launcher for Windows (replaces double-clicking `Iniciar.bat` in scripted workflows).
- `install_secure.ps1`: Secure remote installer — downloads the repo from GitHub over HTTPS, verifies integrity, and delegates to local `install.ps1`. Supports `irm ... | iex` one-liner.
- Restored GitHub Actions CI workflow in `.github/workflows/ci.yml` for dependency install and Python compile checks.
- Added release build workflow in `.github/workflows/release-build.yml` to package a Windows `.exe` and attach it to GitHub Releases.
- Added public roadmap file `ROADMAP.md` with milestones for versions `1.1.0`, `1.2.0`, and `2.0.0`.

### Changed
- Updated `ROADMAP.md` to explicitly separate released versions (`1.0.0`, `1.0.1`, `1.0.2`) from upcoming milestones (`1.1.0`, `1.2.0`, `2.0.0`).
- Refactored project layout to a modular `src/` architecture with compatibility wrappers in root-level `app_*.py` files and `youtube_downloader.py`.
- Updated CI compile checks to validate both transitional wrappers and canonical modules under `src/`.
- Updated release build workflow to package the canonical entrypoint at `src/main/youtube_downloader.py`.
- Updated README project structure table to document the new modular source tree.

### Planned
- Screenshots and visual documentation.

## [1.0.2] - 2026-04-11

### Added
- Bundled portable FFmpeg into the Windows release build so the official `.exe` works out-of-the-box for non-technical users.

### Changed
- Updated the release pipeline to prepare and package FFmpeg binaries inside the executable bundle.
- Updated user documentation to recommend the latest `.exe` as the primary run method, keeping console methods for advanced users.

## [1.1.0] - 2026-04-11

### Added
- Full support for YouTube mix/radio `RD...` URLs as proper playlists.
- Configurable limit for mix/radio queues (`mix_max_videos`, default 100, range 1–100) with UI control in settings.
- All queued (pending) videos displayed in the Downloads tab immediately after detection.
- Visual grouping of pending downloads by playlist batch with header rows and gray background.
- Extra log entry per RD URL showing detected video count.
- `status_pending` i18n key in ES/EN/PT.
- `downloads_group_playlist` and `downloads_group_single` i18n keys for batch headers.
- CI step to explicitly fail when runner uses Python ≥ 3.14.
- PEP 508 Python version markers on all `requirements.txt` entries.

### Fixed
- `NameError: DependencyManager is not defined` in `app_workers.py` (missing import).
- Playlist download regression: single-video workers were downloading entire playlists as one concatenated file.
  - Added `noplaylist: True` to yt-dlp metadata extraction options.
  - Replaced `process_ie_result` with `extract_info` for the download phase to avoid cross-instance `noplaylist` bypass.
- Mix/radio URLs (`watch?v=ID&list=RD...`) were falling back to single-video mode.
  - Root cause: `playlist?list=RD...` returns "This playlist type is unviewable" in yt-dlp.
  - Fix: use original `watch?v=ID&list=RD...` format for extraction.

### Changed
- `Iniciar.bat` now prioritizes `py -3.11`, detects incompatible venv (Python 3.14), recreates it automatically, and installs Python 3.11 via winget if no compatible runtime is found.
- `PyQt6` pinned to `>=6.11.0,<6.12` to prevent DLL mismatch on Windows.
- License changed from MIT to **GNU General Public License v3.0**.

## [1.0.0] - 2026-04-04

### Added
- Public repository structure prepared for GitHub.
- Modular PyQt6 application architecture with separate modules for core logic, workers, dialogs, i18n, logging, and paths.
- Clipboard monitor for automatic YouTube URL detection.
- Concurrent download queue (up to 3 simultaneous downloads).
- Download history tab with status tracking.
- Logs tab for runtime diagnostics.
- Dependency manager with automatic FFmpeg and yt-dlp detection/installation.
- Multilingual interface: Español, English, Português (Brasil).
- Controlled retries and cancellation of active downloads.
- Playlist detection and extraction for `watch?v=...&list=...` URLs.
- Bootstrap script (`Iniciar.bat`) for zero-friction Windows setup.
