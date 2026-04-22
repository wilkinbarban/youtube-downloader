# Roadmap

This roadmap is public and can evolve based on user feedback and maintenance priorities.

## Released versions (completed)

### 1.0.0

Foundation release.

- Modular PyQt6 app structure.
- Download queue and history tabs.
- Logs tab and dependency management.
- Multilingual UI (ES/EN/PT).

### 1.0.1

Release engineering and project maturity improvements.

- CI workflow restored on GitHub Actions.
- Automated Windows executable build workflow.
- Automatic attachment of executable to GitHub Releases.
- Public roadmap and documentation improvements.

### 1.0.2

Out-of-the-box executable experience.

- Bundled portable FFmpeg into the official Windows executable.
- Release pipeline updated to package FFmpeg binaries correctly.
- Documentation updated to prioritize the latest executable.

### 1.1.0

Reliability and quality automation hardening.

- Full support for YouTube mix/radio `RD...` URLs as proper playlists.
- Configurable limit for mix/radio queues, improved pending queue visualization, and related i18n keys.
- Runtime policy hardening for Python compatibility (`>=3.8,<3.14`) across launcher, requirements, and CI.

### 1.2.0

Architecture modularization and release process consolidation.

- Migrated to a canonical modular `src/` source tree with compatibility wrappers at repository root.
- Updated CI compile checks to validate wrappers and canonical modules.
- Consolidated release build workflow and documentation updates for the new structure.
- Fixed application icon resource resolution after the `src/` migration.

### 1.2.1

Root cleanup completion and src-only operational entrypoint.

- Removed legacy root wrappers and consolidated imports to canonical `src.*` modules.
- Standardized launch scripts to run `python -m src.main.youtube_downloader`.
- Updated release packaging to build from `src/main/youtube_downloader.py` with stable import path settings.

### 1.2.2

Support UX modernization and manual update-check release.

- Added manual update check from Help menu against latest GitHub Release.
- Added semantic version comparison service (`src/services/update_service.py`) and single version source (`src/constants.py`).
- Introduced modern support dialog with Wise (ES/EN) and PIX (PT) flows, inline animated feedback, and adaptive geometry hardening for Windows.
- Added coherent iconography across all menu actions.
- Updated i18n and docs to reflect support/update workflow changes.

## Next milestones

## Version 1.3.0

Focus: onboarding and support experience.

- Improve first-run guidance and quick-start messaging.
- Add troubleshooting section for common setup/runtime issues.
- Add optional lightweight diagnostics export from Logs tab.

## Version 2.0.0

Focus: product maturity and extensibility.

- Refactor architecture boundaries between UI and domain layer.
- Add broader automated test coverage (unit + integration).
- Improve download queue controls and resilience under failures.
- Prepare long-term maintainability standards and contributor workflows.
- Deliver a polished release process with stronger QA gates.
