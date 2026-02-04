"""
Formatting utilities for BBOT Server TUI

Reuses existing formatting functions from bbot_server.utils.misc
and provides additional TUI-specific formatters.
"""

from datetime import datetime, timedelta
from typing import Optional, List

# Import existing formatters from the main utils
from bbot_server.utils.misc import timestamp_to_human, seconds_to_human


def format_timestamp(timestamp: float, include_hours: bool = True) -> str:
    """
    Format a Unix timestamp as human-readable string

    Args:
        timestamp: Unix timestamp
        include_hours: Whether to include hour/minute/second

    Returns:
        Formatted timestamp string
    """
    return timestamp_to_human(timestamp, include_hours=include_hours)


def format_duration(seconds: float) -> str:
    """
    Format a duration in seconds as human-readable string

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string (e.g., "2 days, 5 hours")
    """
    return seconds_to_human(seconds)


def format_duration_short(seconds: Optional[float]) -> str:
    """
    Format a duration in a compact format for tables

    Args:
        seconds: Duration in seconds or None

    Returns:
        Compact duration string (e.g., "2d 5h", "5m 23s", "45s")
    """
    if seconds is None:
        return "-"

    if seconds < 0:
        return "-"

    delta = timedelta(seconds=seconds)
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:  # Show seconds if nothing else or as fallback
        parts.append(f"{secs}s")

    # Return first two most significant parts
    return " ".join(parts[:2])


def format_timestamp_short(timestamp: Optional[float]) -> str:
    """
    Format a timestamp in compact format for tables

    Args:
        timestamp: Unix timestamp or None

    Returns:
        Short timestamp string (e.g., "12:34", "Jan 01", "2024-01-01")
    """
    if timestamp is None:
        return "-"

    dt = datetime.fromtimestamp(timestamp)
    now = datetime.now()

    # If today, show just time
    if dt.date() == now.date():
        return dt.strftime("%H:%M")

    # If this year, show month and day
    if dt.year == now.year:
        return dt.strftime("%b %d")

    # Otherwise, show full date
    return dt.strftime("%Y-%m-%d")


def format_list(items: List[str], max_items: int = 3, separator: str = ", ") -> str:
    """
    Format a list of items with truncation

    Args:
        items: List of strings
        max_items: Maximum items to show before truncating
        separator: Separator between items

    Returns:
        Formatted string (e.g., "item1, item2, item3 (+5 more)")
    """
    if not items:
        return "-"

    if len(items) <= max_items:
        return separator.join(items)

    shown = items[:max_items]
    remaining = len(items) - max_items
    return f"{separator.join(shown)} (+{remaining} more)"


def format_number(num: Optional[int], fallback: str = "-") -> str:
    """
    Format a number with thousand separators

    Args:
        num: Number to format or None
        fallback: String to return if num is None

    Returns:
        Formatted number string (e.g., "1,234")
    """
    if num is None:
        return fallback
    return f"{num:,}"


def format_severity(severity: str) -> str:
    """
    Format severity with proper capitalization

    Args:
        severity: Severity level string

    Returns:
        Formatted severity string
    """
    if not severity:
        return "UNKNOWN"
    return severity.upper()


def format_status(status: str) -> str:
    """
    Format scan status with proper capitalization

    Args:
        status: Status string

    Returns:
        Formatted status string
    """
    if not status:
        return "UNKNOWN"
    return status.upper()


def truncate_string(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """
    Truncate a string to maximum length

    Args:
        text: String to truncate
        max_length: Maximum length including suffix
        suffix: Suffix to append if truncated

    Returns:
        Truncated string
    """
    if not text or len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix


def format_host(host: str, max_length: int = 40) -> str:
    """
    Format a hostname for display, truncating if necessary

    Args:
        host: Hostname or IP address
        max_length: Maximum length

    Returns:
        Formatted host string
    """
    if not host:
        return "-"

    if len(host) <= max_length:
        return host

    # For long hostnames, try to keep the important parts
    # e.g., "very-long-subdomain.example.com" -> "very-lo...example.com"
    parts = host.rsplit(".", 2)  # Get last two parts (domain + TLD)
    if len(parts) >= 2:
        suffix = "." + ".".join(parts[-2:])
        prefix_len = max_length - len(suffix) - 3  # 3 for "..."
        if prefix_len > 0:
            return host[:prefix_len] + "..." + suffix

    # Fallback to simple truncation
    return truncate_string(host, max_length)


def format_count_badge(count: int, singular: str = "item", plural: str = "items") -> str:
    """
    Format a count as a badge-style string

    Args:
        count: Number to display
        singular: Singular form of the noun
        plural: Plural form of the noun

    Returns:
        Formatted badge string (e.g., "5 items", "1 item")
    """
    if count == 0:
        return f"0 {plural}"
    if count == 1:
        return f"1 {singular}"
    return f"{count:,} {plural}"
