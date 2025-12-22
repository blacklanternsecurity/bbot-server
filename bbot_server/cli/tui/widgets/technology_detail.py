"""
Technology detail widget for BBOT Server TUI
"""
from textual.app import ComposeResult
from textual.widgets import Static
from textual.containers import VerticalScroll

from bbot_server.cli.tui.utils.formatters import format_timestamp


class TechnologyDetail(VerticalScroll):
    """Widget for displaying detailed technology information"""

    def compose(self) -> ComposeResult:
        """Create the static text widget"""
        yield Static("[dim]No technology selected[/dim]", id="technology-detail-text")

    def update_technology(self, technology) -> None:
        """
        Update the detail view with technology information

        Args:
            technology: Technology model
        """
        try:
            detail_text = self.query_one("#technology-detail-text", Static)
        except:
            return

        if not technology:
            detail_text.update("[dim]No technology selected[/dim]")
            return

        # Build detail text
        details = []

        # Basic info
        details.append(f"[bold]Technology:[/bold] {getattr(technology, 'technology', 'UNKNOWN')}")
        details.append(f"[bold]Host:[/bold] {getattr(technology, 'host', 'N/A')}")

        # Port and netloc
        port = getattr(technology, 'port', 'N/A')
        details.append(f"[bold]Port:[/bold] {port}")

        netloc = getattr(technology, 'netloc', 'N/A')
        details.append(f"[bold]Netloc:[/bold] {netloc}")

        # ID
        tech_id = getattr(technology, 'id', 'N/A')
        details.append(f"[bold]ID:[/bold] {tech_id}")

        # Timestamps
        last_seen = getattr(technology, 'last_seen', 0)
        details.append(f"[bold]Last Seen:[/bold] {format_timestamp(last_seen)}")

        # Type
        tech_type = getattr(technology, 'type', 'N/A')
        details.append(f"[bold]Type:[/bold] {tech_type}")

        # Scope (if available)
        scope = getattr(technology, 'scope', None)
        if scope:
            details.append(f"[bold]Scope:[/bold] {scope}")

        detail_text.update("\n\n".join(details))
