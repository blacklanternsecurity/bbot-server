"""
Color and style utilities for BBOT Server TUI

Defines semantic color constants for Rich markup that match the Textual theme
defined in app.py. Use these constants instead of hard-coding color names.

Theme colors are defined in: bbot_server/cli/tui/app.py (BBOT_THEME)
TCSS variables are in: bbot_server/cli/tui/styles.tcss
"""
from typing import Dict

# =============================================================================
# SEMANTIC COLOR CONSTANTS FOR RICH MARKUP
# =============================================================================
# These match the BBOT_THEME defined in app.py
# Use these in f-strings: f"[{SUCCESS}]text[/{SUCCESS}]"

# Primary theme colors
PRIMARY = "dark_orange"       # #FF8400 - BBOT signature orange
SECONDARY = "grey50"          # #808080 - Grey

# Semantic status colors (for status messages)
SUCCESS = "bright_green"      # #4caf50 - Bright green, readable on dark
ERROR = "red"                 # #f44336 - Red for errors
WARNING = "dark_orange"       # #ffa62b - Orange-yellow warnings
INFO = "cyan"                 # Cyan for informational
LOADING = "cyan"              # Cyan for loading states
MUTED = "grey50"              # Grey for muted/secondary text

# Scan status colors (for Rich markup)
STATUS_RUNNING = "dark_orange"
STATUS_DONE = "bright_green"
STATUS_FAILED = "red"
STATUS_QUEUED = "grey50"
STATUS_CANCELLED = "yellow"
STATUS_STARTING = "cyan"

# Severity colors (for Rich markup in tables/text)
SEVERITY_CRITICAL = "magenta"
SEVERITY_HIGH = "red"
SEVERITY_MEDIUM = "dark_orange"
SEVERITY_LOW = "yellow"
SEVERITY_INFO = "bright_blue"

# Severity level name to score mapping
SEVERITY_LEVELS: Dict[str, int] = {
    "INFO": 1,
    "LOW": 2,
    "MEDIUM": 3,
    "HIGH": 4,
    "CRITICAL": 5,
}

# Textual-compatible severity color mapping
SEVERITY_COLORS_TEXTUAL: Dict[int, str] = {
    1: "bright_blue",         # INFO
    2: "yellow",              # LOW
    3: "dark_orange",         # MEDIUM
    4: "red",                 # HIGH
    5: "magenta",             # CRITICAL
}

SEVERITY_COLORS_CSS: Dict[int, str] = {
    1: "#03a9f4",             # INFO - light blue
    2: "#ffeb3b",             # LOW - yellow
    3: "#ff9800",             # MEDIUM - orange
    4: "#f44336",             # HIGH - red
    5: "#9c27b0",             # CRITICAL - purple
}


# Status colors for scans (Rich markup names)
STATUS_COLORS: Dict[str, str] = {
    "RUNNING": "dark_orange",
    "QUEUED": "grey50",
    "DONE": "bright_green",
    "FAILED": "red",
    "CANCELLED": "yellow",
    "STARTING": "cyan",
}

STATUS_COLORS_CSS: Dict[str, str] = {
    "RUNNING": "#ff9800",     # Orange
    "QUEUED": "#9e9e9e",      # Grey
    "DONE": "#4caf50",        # Green
    "FAILED": "#f44336",      # Red
    "CANCELLED": "#ffeb3b",   # Yellow
    "STARTING": "#00bcd4",    # Cyan
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
    "primary": f"bold {PRIMARY}",
    "secondary": SECONDARY,
    "success": SUCCESS,
    "warning": WARNING,
    "error": ERROR,
    "info": INFO,
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
