"""Compatibility wrapper for the application entry point.

Keeps existing launch scripts and CI commands working while startup code lives
under src/main.
"""

import sys

from src.main.youtube_downloader import main


if __name__ == "__main__":
    sys.exit(main())
