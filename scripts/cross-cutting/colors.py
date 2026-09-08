#!/usr/bin/env python3
"""
scripts/cross-cutting/colors.py

Shared ANSI color palette for repo py scripts. Cross-cutting (not tied to
any one stack) — import from here instead of redefining escape codes
per-script.
"""

YELLOW = "\033[33m"
RED_ORANGE = "\033[38;5;202m"
GREEN = "\033[32m"
BLUE = "\033[38;5;39m"
CYAN = "\033[36m"
RESET = "\033[0m"
