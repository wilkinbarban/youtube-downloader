# AGENTS.md

## Project Variables

Before starting any work, the AI must read these values and apply them throughout the entire session.
Do not assume values that are not declared here.

```
PROJECT_NAME     = "YouTube Downloader"
STACK            = "Python + PyQt6"
RUNTIME_POLICY   = "Python >=3.8, <3.15, recommended 3.11"
PACKAGE_MANAGER  = "pip / requirements.txt"
MAIN_ENTRY       = "src/main/youtube_downloader.py"
BUILD_TOOL       = "PyInstaller"
BUNDLED_DEPS     = "FFmpeg"
PLATFORMS        = "Windows 10/11"
LICENSE_TYPE     = "GPL-3.0"
EDUCATIONAL      = true
REPO_URL         = "https://github.com/wilkinbarban/youtube-downloader"
AUTHOR_NAME      = "Wilkin Barban Rosabal"
AUTHOR_EMAIL     = "wilkin.barban@gmail.com"
LANGUAGES_UI     = "ES / EN / PT"
```

---

## Purpose

This file defines the mandatory AI workflow for this project.

It enforces:
- strict context-first execution,
- complete technical and documentation traceability,
- professional multilingual documentation (ES/EN/PT),
- reproducible CI/CD and release process,
- final executable distribution with dependencies bundled,
- persistent AI operational memory through `memoria.mc`.

## Scope

Apply these rules to all AI work in this project:
- analysis,
- code changes,
- architecture changes,
- scripts,
- docs,
- CI/CD,
- release operations.

## Mandatory Operating Rules

### Rule 1: Read Memory First
Before any analysis or modification, the AI must read `memoria.mc`.

### Rule 2: No Work Without Real Context
The AI must not assume project state from prior chat memory only.
It must validate current repository files before acting.

### Rule 3: Update Memory After Every Visible Change
After any change in code, docs, scripts, workflows, release assets, compatibility, or user-visible behavior, the AI must append a new log entry to `memoria.mc`.

### Rule 4: Preserve Memory History
The AI must never delete relevant history from `memoria.mc`.
It must append continuity records (problem, cause, fix, validation).

### Rule 5: Keep Cross-File Consistency
The AI must keep consistency between:
- `memoria.mc`
- source code
- `README.md`
- `requirements.txt`
- installers and runtime scripts
- CI/CD workflows
- `CHANGELOG.md`
- `ROADMAP.md`

### Rule 6: No Invented Dependencies or Capabilities
Dependencies and features documented must exist in real code and `requirements.txt`.

### Rule 7: Document with Signal, Not Noise
Prefer useful docs, comments, and docstrings.
Avoid trivial comments and vague release notes.

### Rule 8: Register Compatibility Impact
If a change affects compatibility, installation, runtime behavior, or release process, reflect it in:
- `memoria.mc`
- `README.md` (if user-facing)
- `CHANGELOG.md` (if release-relevant)

### Rule 9: Validate After Editing
When possible, validate edits with compile/import/tests/lint/build checks.
No task is complete without at least one validation step.

### Rule 10: This File Governs Future Sessions
Treat this file as the AI operating policy for this project.
Its reading is mandatory before continuing any work.

## Baseline Project Governance Files

The AI must create and maintain:
- `README.md` (trilingual: Spanish, English, Portuguese)
- `CHANGELOG.md` (Keep a Changelog + SemVer)
- `ROADMAP.md` (released versions + upcoming milestones)
- `LICENSE`
- `SECURITY.md` (explicit educational-purpose policy)
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`

## Required Documentation Pattern

### README Structure
The AI must keep a professional README with:
- project identity and badges,
- educational disclaimer,
- language sections (ES/EN/PT),
- recommended usage path (latest release executable),
- installation options (local and one-command remote),
- dependency notes (FFmpeg policy),
- screenshots,
- project structure table,
- license section.

### CHANGELOG Strategy
- Use Semantic Versioning: `1.0.0`, `1.0.1`, `1.0.2`, etc.
- Maintain `[Unreleased]` and released sections.
- Record Added/Changed/Fixed clearly.

### ROADMAP Strategy
- Separate:
  - released versions (completed),
  - next milestones (planned).
- Do not keep already completed work as future roadmap items.

## Multilingual Standard (ES/EN/PT)

The AI must ensure multilingual consistency across:
- core user documentation,
- major user-facing messages,
- interface labels/dialogs,
- help/manual text.

Maintain synchronized ES/EN/PT keys in `app_i18n.py`.

## Installer and Bootstrap Standard

Provide and maintain:
- `install.ps1`: unified secure installer/launcher for both local repository setup and remote HTTPS-based one-command installations.

Installer design must:
- enforce compatible runtime policy (Python >=3.8, <3.14),
- create/repair isolated `.venv` when needed,
- install dependencies from `requirements.txt`,
- start `src/main/youtube_downloader.py`,
- fail with clear errors.

## CI/CD and Release Standard

Maintain:
- `.github/workflows/ci.yml`: CI for install + compile checks.
- `.github/workflows/release-build.yml`: automated build + auto-attach `.exe` to GitHub Releases.

Final delivery must include:
- `YouTubeDownloader.exe` packaged with PyInstaller,
- FFmpeg binaries bundled inside the executable,
- release notes aligned with actual bundled behavior.

## Executable Packaging Rule (Critical Final Step)

- Package FFmpeg binaries into the release executable.
- Validate executable runs without manual dependency setup.
- Align README and release notes with actual packaging behavior.
- Verify release asset SHA256 and size when possible.

This packaging and validation step is mandatory before marking release work complete.

## Release Operations Checklist

Before publishing a release:
- verify docs are updated,
- verify changelog section for target version,
- verify roadmap consistency,
- run validation checks,
- build artifact,
- upload/attach artifact,
- verify release notes,
- log final release details in `memoria.mc`.

After publishing:
- confirm release URL and artifact metadata,
- update any outdated links in README.

## AI Memory Files Policy (Local AI-only)

These files are AI operational memory only and must NOT be uploaded to GitHub:
- `memoria.mc`
- `AGENTS_1.MD`

`.gitignore` must exclude them.
`AGENTS.md` is intentionally version-controlled as the project policy document.

## Operational Work Sequence (Small to Complex)

1. Read `memoria.mc`.
2. Read relevant project files.
3. Confirm requirements and constraints.
4. Implement minimal safe changes first.
5. Validate immediately.
6. Update docs affected by the change.
7. Update `CHANGELOG.md` and `ROADMAP.md` when required.
8. Append structured log to `memoria.mc`.
9. Prepare release automation adjustments if needed.
10. Build final distributable artifact.
11. Verify release asset and notes.
12. Publish and push final changes.

## Quality Bar

The AI must prioritize:
- correctness,
- reproducibility,
- clean architecture boundaries,
- professional documentation,
- release reliability,
- multilingual consistency,
- production-ready distribution experience.

## Enforcement Intent

This policy exists to force consistent, elegant, and traceable AI execution across all sessions of this project.
