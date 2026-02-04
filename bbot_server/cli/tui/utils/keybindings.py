"""
Keyboard binding definitions for BBOT Server TUI

Centralizes all keyboard shortcuts and their descriptions for
consistency across the application.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class KeyBinding:
    """Represents a keyboard binding"""

    key: str
    action: str
    description: str
    priority: bool = False


# Global navigation bindings (available on all screens)
GLOBAL_BINDINGS: List[KeyBinding] = [
    KeyBinding("q", "quit", "Quit", priority=True),
    KeyBinding("d", "show_dashboard", "Dashboard"),
    KeyBinding("s", "show_scans", "Scans"),
    KeyBinding("a", "show_assets", "Assets"),
    KeyBinding("f", "show_findings", "Findings"),
    KeyBinding("v", "show_activity", "Activity"),
    KeyBinding("?", "show_help", "Help"),
]


# Screen-specific bindings
SCAN_BINDINGS: List[KeyBinding] = [
    KeyBinding("r", "refresh", "Refresh"),
    KeyBinding("enter", "show_details", "Details"),
    KeyBinding("/", "focus_filter", "Filter"),
]

ASSET_BINDINGS: List[KeyBinding] = [
    KeyBinding("r", "refresh", "Refresh"),
    KeyBinding("enter", "show_details", "Details"),
    KeyBinding("/", "focus_filter", "Filter"),
    KeyBinding("i", "toggle_inscope", "In-Scope Only"),
]

FINDING_BINDINGS: List[KeyBinding] = [
    KeyBinding("r", "refresh", "Refresh"),
    KeyBinding("enter", "show_details", "Details"),
    KeyBinding("/", "focus_filter", "Filter"),
    KeyBinding("1", "filter_info", "Show INFO"),
    KeyBinding("2", "filter_low", "Show LOW+"),
    KeyBinding("3", "filter_medium", "Show MEDIUM+"),
    KeyBinding("4", "filter_high", "Show HIGH+"),
    KeyBinding("5", "filter_critical", "Show CRITICAL"),
]

ACTIVITY_BINDINGS: List[KeyBinding] = [
    KeyBinding("space", "toggle_pause", "Pause/Resume"),
    KeyBinding("c", "clear_feed", "Clear"),
    KeyBinding("/", "focus_filter", "Filter"),
    KeyBinding("r", "refresh", "Refresh"),
]

DASHBOARD_BINDINGS: List[KeyBinding] = [
    KeyBinding("r", "refresh", "Refresh"),
]


def get_bindings_for_screen(screen_name: str) -> List[KeyBinding]:
    """
    Get keyboard bindings for a specific screen

    Args:
        screen_name: Name of the screen

    Returns:
        List of KeyBinding objects
    """
    screen_bindings = {
        "scans": SCAN_BINDINGS,
        "assets": ASSET_BINDINGS,
        "findings": FINDING_BINDINGS,
        "activity": ACTIVITY_BINDINGS,
        "dashboard": DASHBOARD_BINDINGS,
    }

    return screen_bindings.get(screen_name, [])


def format_key_hint(bindings: List[KeyBinding], max_hints: int = 8) -> str:
    """
    Format key bindings as a hint string for status bar

    Args:
        bindings: List of KeyBinding objects
        max_hints: Maximum number of hints to show

    Returns:
        Formatted hint string (e.g., "n:New r:Refresh ?:Help")
    """
    hints = []
    for binding in bindings[:max_hints]:
        # Use short key names
        key = binding.key
        if key == "enter":
            key = "↵"
        elif key == "space":
            key = "␣"
        elif key == "escape":
            key = "Esc"

        hints.append(f"{key}:{binding.description}")

    return " ".join(hints)


def get_help_text(screen_name: str = None) -> str:
    """
    Get formatted help text for keyboard shortcuts

    Args:
        screen_name: Optional screen name for screen-specific help

    Returns:
        Multi-line help text
    """
    lines = ["Keyboard Shortcuts", "=" * 40, ""]

    # Global bindings
    lines.append("Global:")
    for binding in GLOBAL_BINDINGS:
        lines.append(f"  {binding.key:15} {binding.description}")

    # Screen-specific bindings
    if screen_name:
        screen_bindings = get_bindings_for_screen(screen_name)
        if screen_bindings:
            lines.append("")
            lines.append(f"{screen_name.title()} Screen:")
            for binding in screen_bindings:
                lines.append(f"  {binding.key:15} {binding.description}")

    return "\n".join(lines)
