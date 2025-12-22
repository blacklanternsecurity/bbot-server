"""
Event detail widget for BBOT Server TUI
"""
from textual.app import ComposeResult
from textual.widgets import Static
from textual.containers import VerticalScroll

from bbot_server.cli.tui.utils.formatters import format_timestamp


class EventDetail(VerticalScroll):
    """Widget for displaying detailed event information"""

    def compose(self) -> ComposeResult:
        """Create the static text widget"""
        yield Static("[dim]No event selected[/dim]", id="event-detail-text")

    def update_event(self, event) -> None:
        """
        Update the detail view with event information

        Args:
            event: Event model
        """
        try:
            detail_text = self.query_one("#event-detail-text", Static)
        except:
            return

        if not event:
            detail_text.update("[dim]No event selected[/dim]")
            return

        # Build detail text
        details = []

        # Basic info
        details.append(f"[bold]Type:[/bold] {getattr(event, 'type', 'UNKNOWN')}")
        details.append(f"[bold]Data:[/bold] {getattr(event, 'data', 'N/A')}")
        details.append(f"[bold]Host:[/bold] {getattr(event, 'host', 'N/A')}")

        # Scan info
        scan_id = getattr(event, 'scan', 'N/A')
        details.append(f"[bold]Scan ID:[/bold] {scan_id}")

        # Timestamps
        timestamp = getattr(event, 'timestamp', 0)
        details.append(f"[bold]Timestamp:[/bold] {format_timestamp(timestamp)}")

        # Source
        source = getattr(event, 'source', 'N/A')
        details.append(f"[bold]Source:[/bold] {source}")

        # Tags
        tags = getattr(event, 'tags', [])
        if tags:
            tags_str = ", ".join(tags)
            details.append(f"[bold]Tags:[/bold] {tags_str}")

        # Module
        module = getattr(event, 'module', 'N/A')
        details.append(f"[bold]Module:[/bold] {module}")

        # Parent
        parent = getattr(event, 'parent', 'N/A')
        details.append(f"[bold]Parent:[/bold] {parent}")

        # Discovery info
        discovery_context = getattr(event, 'discovery_context', 'N/A')
        details.append(f"[bold]Discovery Context:[/bold] {discovery_context}")

        discovery_path = getattr(event, 'discovery_path', [])
        if discovery_path:
            path_str = " → ".join(discovery_path)
            details.append(f"[bold]Discovery Path:[/bold] {path_str}")

        detail_text.update("\n\n".join(details))
