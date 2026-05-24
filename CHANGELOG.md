# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

### [1.3.0] - 2026-05-23

### Added
- **Python 3.14 Support**: Expanded runtime policy and compatibility ceiling to `<3.15` to officially support Python 3.14.x runtimes (tested with Python 3.14.5).
- **Web Asynchronous Manager**: Integrated FastAPI + Uvicorn server running as a background `QThread` (`FastApiServerWorker`).
  - Exposed a modern web client interface at `http://127.0.0.1:8000` styled with glassmorphism, responsive cards, neon gradients, and a live console logger.
  - Developed real-time WebSocket connection (`/api/ws`) for bidirectional communication and instantaneous progress bar updates, falling back automatically to 3-second REST polling if disconnected.
  - Added REST API endpoints for queue management (adding tasks, pausing/resuming queue, cancelling active downloads, clearing history), configuration updating, and log retrieval.
  - Interactive **Web Manager** launcher added to the **Tools** menu of the PyQt6 desktop app.
  - Added FastAPI, Uvicorn, Websockets, and Pydantic as official project dependencies.
- **Robust Error Handling System**:
  - Implemented custom exception hierarchy inheriting from `YtdlAppError` (`src/utils/errors.py`), including specific domains for dependencies, extraction (`PrivateVideoError`, `AgeRestrictedError`, `BotChallengeError`), downloads (`NetworkTimeoutError`, `DiskSpaceError`, `PermissionDeniedError`), and configuration (`ConfigError`).
  - Added a type-safe `Result[T, E]` pattern for functional error/success flow handling.
  - Replaced broad exceptions with explicit error mappings via `map_ytdlp_error()`.
  - Implemented custom `@retry` decorator with exponential backoff for network-bound tasks (`src/utils/decorators.py`).
  - Integrated global exception handling middleware in FastAPI (`src/web/app.py`) for clean localized JSON error responses.
  - Localized background worker errors dynamically using trilingual i18n keys inside `DownloadManager` before saving to history.

### Bot-Bypass via Cookies System (Feature Breakdown)
To combat YouTube's strict bot-detection rules (*"Sign in to confirm you’re not a bot"* challenges), a comprehensive cookies integration layer has been designed and implemented:
1. **Automated Browser Cookie Extraction**:
   - Added `cookies_browser` config option supporting Chrome, Firefox, Edge, Brave, and Opera.
   - The extraction and download modules automatically inject `cookiesfrombrowser: (selected_browser)` into the `yt-dlp` constructor, allowing headless requests to carry authentication headers from the user's active browser.
2. **Local Netscape format (`cookies.txt`) Fallback**:
   - Because Windows locks Chromium-based SQLite cookie databases (Chrome/Edge) while the browser is running, direct database reading can raise a lock error (`Could not copy Chrome cookie database`).
   - To solve this, the app detects a local `cookies.txt` file in Netscape format in the project base directory (`BASE_DIR`). If found, it takes precedence and is injected into the download engine via the `cookiefile` parameter, bypassing browser access entirely.
3. **Automated JSON-to-Netscape Converter**:
   - Since Chrome/Edge extensions commonly export cookies in JSON format (`cookies.json`), which `yt-dlp` cannot parse directly, we implemented an automatic converter `check_and_convert_json_cookies()` in `src/modules/core.py`.
   - The converter checks for a `cookies.json` file in the root directory. If found, it parses the standard JSON array (matching fields: `domain`, `path`, `secure`, `expirationDate` or `expiry`, `name`, `value`), transforms it into the tab-separated Netscape format structure, and saves it as `cookies.txt`.
   - The conversion is run automatically at application boot, bat startup scripts, and whenever a download worker is initialized.
4. **Interactive Interfaces**:
   - **PyQt6 (ConfigDialog)**: Added a cookie status indicator (`Active cookies.txt`, `Pending conversion cookies.json`, or `No cookies`) and an "Importar cookies..." button that lets users select either `.json` or `.txt` files, copies them to the root directory, performs the conversion on-the-fly, and displays instant feedback.
   - **Web Manager Client**: Exposed endpoints `GET /api/config/cookies/status` and `POST /api/config/cookies` allowing users to upload cookies files from their web browsers, which are parsed and processed by the backend.

### Changed
- Updated User Guide in Spanish, English, and Portuguese to include detailed troubleshooting steps for YouTube bot blocks and browser cookie database locks.
- **Nebula-Cyberpunk UI Design**: Unified and modernized the visual design of both the Web Manager and the PyQt6 Desktop application using glassmorphism, glowing accents, neon dynamic backgrounds/borders, customized scrollbars, and styled linear progress bars.
- **Unified PyQt6 Dialogs**: Redesigned dialogs (`ConfigDialog`, `DependenciesDialog`, `HelpDialog`, and `SupportDialog`) in `dialogs.py` to group settings inside distinct card layouts with structured alignments, themed action buttons (primary gradient / red cancel style), and a portable base64 SVG checkmark for checkboxes.

## [1.2.2] - 2026-04-22

### Added
- Manual update-check system from **Help** menu with semantic version comparison against latest GitHub Release.
- New service module `src/services/update_service.py` to isolate network/update business logic from UI.
- Version constant module `src/constants.py` as single source of truth (`VERSION = "1.2.2"`).
- New multilingual i18n keys (ES/EN/PT) for update-check action and dialogs.
- Consistent menu iconography across all top menu actions using standard Qt icons.
- New support icon asset: `assets/support.svg`.

### Changed
- Replaced legacy donation popup flow with a modern support dialog (`SupportDialog`) integrated into app styling.
- Updated support behavior by locale:
	- ES/EN: Wise payment link (`https://wise.com/pay/me/wilkinb3`) with open/copy actions.
	- PT: PIX key flow (`wilkin.barban@yahoo.com`) with copy action.
- Reworked support dialog UX: hero card + QR card layout, larger QR preview, compact action buttons, and inline animated feedback for copy actions.
- Hardened support dialog geometry handling on Windows to avoid `QWindowsWindow::setGeometry` warnings on constrained displays.
- Added dependencies for new features:
	- `requests>=2.28.0`
	- `packaging>=23.0`
	- `qrcode[pil]>=7.4`
	- `Pillow>=9.0.0`

### Fixed
- Removed author email from About text in ES/EN/PT.
- Unified copy-feedback behavior across languages in support dialog (consistent inline banner behavior for ES/EN/PT).

## [1.2.1] - 2026-04-12

### Changed
- Removed legacy root-level compatibility wrappers (`app_*.py` and `youtube_downloader.py`) after migrating all internal imports and launch/build entrypoints to canonical `src.*` modules.
- Updated launch scripts (`Iniciar.bat`, `install.ps1`) to start the app with `python -m src.main.youtube_downloader`.
- Updated release build to package from `src/main/youtube_downloader.py` using `--paths "."` for stable import resolution.

## [1.2.0] - 2026-04-12

### Added
- `install.ps1`: PowerShell one-command installer and launcher for Windows (replaces double-clicking `Iniciar.bat` in scripted workflows).
- `install_secure.ps1`: Secure remote installer - downloads the repo from GitHub over HTTPS, verifies integrity, and delegates to local `install.ps1`. Supports `irm ... | iex` one-liner.
- Restored GitHub Actions CI workflow in `.github/workflows/ci.yml` for dependency install and Python compile checks.
- Added release build workflow in `.github/workflows/release-build.yml` to package a Windows `.exe` and attach it to GitHub Releases.
- Added public roadmap file `ROADMAP.md` with milestones for versions `1.1.0`, `1.2.0`, and `2.0.0`.

### Changed
- Updated `ROADMAP.md` to explicitly separate released versions (`1.0.0`, `1.0.1`, `1.0.2`) from upcoming milestones (`1.1.0`, `1.2.0`, `2.0.0`).
- Refactored project layout to a modular `src/` architecture with compatibility wrappers in root-level `app_*.py` files and `youtube_downloader.py`.
- Updated CI compile checks to validate both transitional wrappers and canonical modules under `src/`.
- Updated release build workflow to package the executable from the stable root entrypoint `youtube_downloader.py`.
- Updated README project structure table to document the new modular source tree.

### Fixed
- Fixed application icon loading in development after the `src/` refactor by correcting resource base path resolution in `src/config/paths.py`.

## [1.1.0] - 2026-04-11

### Added
- Full support for YouTube mix/radio `RD...` URLs as proper playlists.
- Configurable limit for mix/radio queues (`mix_max_videos`, default 100, range 1–100) with UI control in settings.
- All queued (pending) videos displayed in the Downloads tab immediately after detection.
- Visual grouping of pending downloads by playlist batch with header rows and gray background.
- Extra log entry per RD URL showing detected video count.
- `status_pending` i18n key in ES/EN/PT.
- `downloads_group_playlist` and `downloads_group_single` i18n keys for batch headers.
- CI step to explicitly fail when runner uses Python >= 3.14.
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

## [1.0.2] - 2026-04-11

### Added
- Bundled portable FFmpeg into the Windows release build so the official `.exe` works out-of-the-box for non-technical users.

### Changed
- Updated the release pipeline to prepare and package FFmpeg binaries inside the executable bundle.
- Updated user documentation to recommend the latest `.exe` as the primary run method, keeping console methods for advanced users.

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
