"""
Color and style utilities for BBOT Server TUI

Maps BBOT Server color schemes to Textual-compatible styles.
Reuses existing color constants from the CLI theme.
"""
from typing import Dict

# Import existing theme colors

# Import severity colors from findings models
try:
    from bbot_server.modules.findings.findings_models import SEVERITY_COLORS, SEVERITY_LEVELS
except ImportError:
    # Fallback if models aren't loaded yet
    SEVERITY_COLORS = {
        1: "deep_sky_blue1",   # INFO
        2: "gold1",             # LOW
        3: "dark_orange",       # MEDIUM
        4: "bright_red",        # HIGH
        5: "purple",            # CRITICAL
    }
    SEVERITY_LEVELS = {
        "INFO": 1,
        "LOW": 2,
        "MEDIUM": 3,
        "HIGH": 4,
        "CRITICAL": 5,
    }


# BBOT Theme colors (from existing CLI)
PRIMARY_COLOR = "#FF8400"  # dark orange
SECONDARY_COLOR = "#808080"  # grey50


# Textual-compatible severity color mapping
SEVERITY_COLORS_TEXTUAL: Dict[int, str] = {
    1: "blue",              # INFO
    2: "yellow",            # LOW
    3: "bright_magenta",    # MEDIUM (orange-ish)
    4: "red",               # HIGH
    5: "magenta",           # CRITICAL (purple)
}

SEVERITY_COLORS_CSS: Dict[int, str] = {
    1: "deepskyblue",       # INFO
    2: "gold",              # LOW
    3: "darkorange",        # MEDIUM
    4: "red",               # HIGH
    5: "purple",            # CRITICAL
}


# Status colors for scans
STATUS_COLORS: Dict[str, str] = {
    "RUNNING": "bright_magenta",  # orange-ish
    "QUEUED": "white",
    "DONE": "green",
    "FAILED": "red",
    "CANCELLED": "yellow",
    "STARTING": "cyan",
}

STATUS_COLORS_CSS: Dict[str, str] = {
    "RUNNING": "darkorange",
    "QUEUED": "grey",
    "DONE": "green",
    "FAILED": "red",
    "CANCELLED": "yellow",
    "STARTING": "cyan",
}


def get_severity_color(severity_score: int) -> str:
    """
    Get Textual color for a severity score

    Args:
        severity_score: Severity level (1-5)

    Returns:
        Textual color name
    """
    return SEVERITY_COLORS_TEXTUAL.get(severity_score, "white")


def get_severity_css_color(severity_score: int) -> str:
    """
    Get CSS color for a severity score

    Args:
        severity_score: Severity level (1-5)

    Returns:
        CSS color name
    """
    return SEVERITY_COLORS_CSS.get(severity_score, "white")


def get_severity_score(severity_name: str) -> int:
    """
    Get severity score from name

    Args:
        severity_name: Severity level name (e.g., "HIGH")

    Returns:
        Severity score (1-5)
    """
    return SEVERITY_LEVELS.get(severity_name.upper(), 1)


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
    return f"[{color}]{text}[/{color}]"


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


# Rich console markup colors (for direct terminal output)
RICH_COLORS = {
    "primary": "bold dark_orange",
    "secondary": "grey50",
    "success": "green",
    "warning": "yellow",
    "error": "red",
    "info": "cyan",
}


def get_rich_color(name: str) -> str:
    """
    Get Rich console color by name

    Args:
        name: Color name (primary, secondary, success, warning, error, info)

    Returns:
        Rich color string
    """
    return RICH_COLORS.get(name, "white")
