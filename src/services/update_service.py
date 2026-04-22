"""Manual update-check service using GitHub Releases API."""

from __future__ import annotations

from typing import Dict

import requests
from packaging.version import InvalidVersion, Version


class UpdateService:
    """Encapsulates update-check logic separated from UI concerns."""

    _DEFAULT_REPO = "wilkinbarban/youtube-downloader"
    _TIMEOUT_SECONDS = 5

    @staticmethod
    def _normalize_version_tag(tag: str) -> str:
        """Normalize release tags so semantic comparison remains reliable."""
        if not tag:
            return ""
        normalized = str(tag).strip()
        if normalized.lower().startswith("v"):
            normalized = normalized[1:]
        return normalized

    @staticmethod
    def _latest_release_api_url(repo: str) -> str:
        return f"https://api.github.com/repos/{repo}/releases/latest"

    @staticmethod
    def check_for_updates(current_version: str, repo: str | None = None) -> Dict[str, str]:
        """
        Compare local version with latest GitHub release.

        Returns one of three statuses:
        - available: newer release exists
        - up_to_date: local version is latest or newer
        - error: network/API/parsing failure
        """
        repo_name = (repo or UpdateService._DEFAULT_REPO).strip()
        url = UpdateService._latest_release_api_url(repo_name)

        try:
            response = requests.get(url, timeout=UpdateService._TIMEOUT_SECONDS)
            response.raise_for_status()
            payload = response.json()

            latest_tag = payload.get("tag_name") or payload.get("name") or ""
            latest_version_text = UpdateService._normalize_version_tag(latest_tag)
            current_version_text = UpdateService._normalize_version_tag(current_version)

            latest_version = Version(latest_version_text)
            local_version = Version(current_version_text)

            release_url = payload.get("html_url") or f"https://github.com/{repo_name}/releases/latest"

            if latest_version > local_version:
                return {
                    "status": "available",
                    "latest": str(latest_version),
                    "current": str(local_version),
                    "url": release_url,
                }

            return {
                "status": "up_to_date",
                "latest": str(latest_version),
                "current": str(local_version),
                "url": release_url,
            }

        except (requests.RequestException, ValueError, InvalidVersion) as exc:
            return {
                "status": "error",
                "error": str(exc),
            }
