"""
Color and style utilities for BBOT Server TUI

Defines semantic color constants for Rich markup that match the Textual theme
defined in app.py. Use these constants instead of hard-coding color names.

Theme colors are defined in: bbot_server/cli/tui/app.py (BBOT_THEME)
TCSS variables are in: bbot_server/cli/tui/styles.tcss
"""

import logging
from typing import Dict

log = logging.getLogger("bbot_server.tui.colors")

# =============================================================================
# SEMANTIC COLOR CONSTANTS FOR RICH MARKUP
# =============================================================================
# These match the BBOT_THEME defined in app.py
# Use these in f-strings: f"[{SUCCESS}]text[/{SUCCESS}]"

# Semantic status colors (for status messages) - using hex codes for reliability
SUCCESS = "#4caf50"  # Bright green, readable on dark
ERROR = "#f44336"  # Red for errors
WARNING = "#ffa62b"  # Orange-yellow warnings
INFO = "#00bcd4"  # Cyan for informational
LOADING = "#00bcd4"  # Cyan for loading states
MUTED = "#808080"  # Grey for muted/secondary text

# Severity level name to score mapping
SEVERITY_LEVELS: Dict[str, int] = {
    "INFO": 1,
    "LOW": 2,
    "MEDIUM": 3,
    "HIGH": 4,
    "CRITICAL": 5,
}

# Single source of truth for severity colors (matches TCSS $severity-* variables)
SEVERITY_COLORS: Dict[int, str] = {
    1: "#03a9f4",  # INFO - light blue
    2: "#ffeb3b",  # LOW - yellow
    3: "#ff9800",  # MEDIUM - orange
    4: "#f44336",  # HIGH - red
    5: "#9c27b0",  # CRITICAL - purple
}


# Status colors for scans (using hex codes to match working severity colors)
STATUS_COLORS: Dict[str, str] = {
    "RUNNING": "#ff9800",  # Orange
    "QUEUED": "#9e9e9e",  # Grey
    "DONE": "#4caf50",  # Green
    "FAILED": "#f44336",  # Red
    "CANCELLED": "#ffeb3b",  # Yellow
    "STARTING": "#00bcd4",  # Cyan
}

STATUS_COLORS_CSS: Dict[str, str] = {
    "RUNNING": "#ff9800",  # Orange
    "QUEUED": "#9e9e9e",  # Grey
    "DONE": "#4caf50",  # Green
    "FAILED": "#f44336",  # Red
    "CANCELLED": "#ffeb3b",  # Yellow
    "STARTING": "#00bcd4",  # Cyan
}


def get_severity_color(severity_score: int) -> str:
    """
    Get color for a severity score

    Args:
        severity_score: Severity level (1-5)

    Returns:
        Hex color code
    """
    color = SEVERITY_COLORS.get(severity_score, "white")
    return color


def get_severity_score(severity_name: str) -> int:
    """
    Get severity score from name

    Args:
        severity_name: Severity level name (e.g., "HIGH")

    Returns:
        Severity score (1-5)
    """
    upper_name = severity_name.upper()
    score = SEVERITY_LEVELS.get(upper_name, 1)
    return score


def get_status_color(status: str) -> str:
    """
    Get Textual color for a scan status

    Args:
        status: Status string (e.g., "RUNNING")

    Returns:
        Textual color name
    """
    return STATUS_COLORS.get(status.upper(), "white")


def get_status_css_color(status: str) -> str:
    """
    Get CSS color for a scan status

    Args:
        status: Status string (e.g., "RUNNING")

    Returns:
        CSS color name
    """
    return STATUS_COLORS_CSS.get(status.upper(), "white")


def colorize_severity(severity_name: str, text: str) -> str:
    """
    Wrap text in Rich markup with severity color

    Args:
        severity_name: Severity level name
        text: Text to colorize

    Returns:
        Rich markup string
    """
    score = get_severity_score(severity_name)
    color = get_severity_color(score)
    result = f"[{color}]{text}[/{color}]"
    return result


def colorize_status(status: str, text: str) -> str:
    """
    Wrap text in Rich markup with status color

    Args:
        status: Status string
        text: Text to colorize

    Returns:
        Rich markup string
    """
    color = get_status_color(status)
    return f"[{color}]{text}[/{color}]"


def get_severity_class(severity_score: int) -> str:
    """
    Get CSS class name for severity

    Args:
        severity_score: Severity level (1-5)

    Returns:
        CSS class name
    """
    severity_names = {1: "info", 2: "low", 3: "medium", 4: "high", 5: "critical"}
    name = severity_names.get(severity_score, "info")
    return f"severity-{name}"


def get_status_class(status: str) -> str:
    """
    Get CSS class name for status

    Args:
        status: Status string

    Returns:
        CSS class name
    """
    return f"status-{status.lower()}"


# =============================================================================
# HELPER FUNCTIONS FOR COMMON MARKUP PATTERNS
# =============================================================================


def success_text(text: str) -> str:
    """Wrap text in success (green) color markup"""
    return f"[{SUCCESS}]{text}[/{SUCCESS}]"


def error_text(text: str) -> str:
    """Wrap text in error (red) color markup"""
    return f"[{ERROR}]{text}[/{ERROR}]"


def warning_text(text: str) -> str:
    """Wrap text in warning (orange) color markup"""
    return f"[{WARNING}]{text}[/{WARNING}]"


def info_text(text: str) -> str:
    """Wrap text in info (cyan) color markup"""
    return f"[{INFO}]{text}[/{INFO}]"


def muted_text(text: str) -> str:
    """Wrap text in muted (grey) color markup"""
    return f"[{MUTED}]{text}[/{MUTED}]"


def loading_text(text: str) -> str:
    """Wrap text in loading (cyan) color markup"""
    return f"[{LOADING}]{text}[/{LOADING}]"
