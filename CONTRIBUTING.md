# Contributing

Thanks for considering a contribution.

## Important notice

This is an **educational project** demonstrating Python desktop application development with PyQt6.
By submitting a contribution, you agree to license your work under the **GNU General Public License v3.0**, the same license used by this project.

## Scope

Contributions should improve code quality, reliability, documentation, packaging, or user experience. Do not add features that encourage bypassing platform terms of service or that introduce security vulnerabilities.

## Before you start

- Read the README, SECURITY policy, and educational disclaimer.
- Open an issue before starting large changes.
- Keep pull requests focused and easy to review.
- Ensure your changes are compatible with Windows.

## Setup

### Windows

Double-click `Iniciar.bat` — it handles Python verification, virtual environment creation, and dependency installation automatically.

Alternatively, set up manually:

```cmd
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m src.main.youtube_downloader
```

Run a syntax check before submitting:

```cmd
python -m py_compile src\__init__.py src\main\__init__.py src\main\youtube_downloader.py src\config\__init__.py src\config\paths.py src\config\i18n.py src\utils\__init__.py src\utils\logging.py src\services\__init__.py src\services\dependencies.py src\services\workers.py src\modules\__init__.py src\modules\core.py src\modules\ui\__init__.py src\modules\ui\dialogs.py src\modules\ui\main_window.py
```

## Coding guidelines

- Prefer small, reviewable commits.
- Keep the architecture modular.
- Avoid unrelated refactors in the same pull request.
- Preserve the native PyQt6 desktop feel unless a UI change is explicitly required.
- Document user-visible behavior changes in the README or CHANGELOG.
- Only use libraries fully compatible with Windows and the project's Python policy (`>=3.8, <3.15`).
- All new code comments and docstrings must be written in **English**.

## Pull request checklist

- [ ] The change is scoped and explained clearly.
- [ ] The app compiles cleanly: `py_compile` passes on all modules.
- [ ] Docs updated if behavior changed (README and/or CHANGELOG).
- [ ] No new dependencies added without updating `requirements.txt`.

- The PR title is descriptive.

## Commit style

Recommended examples:

- `fix: handle YouTube radio URLs as single-video fallback`
- `docs: add GitHub contribution and security policies`
- `refactor: split UI and workers into separate modules`