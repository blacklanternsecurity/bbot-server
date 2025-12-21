"""
Finding detail panel widget for BBOT Server TUI
"""
from textual.widgets import Static
from textual.containers import Container

from bbot_server.cli.tui.utils.formatters import format_timestamp
from bbot_server.cli.tui.utils.colors import colorize_severity


class FindingDetail(Container):
    """Widget for displaying detailed finding information"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._current_finding = None

    def compose(self):
        """Create child widgets"""
        yield Static("", id="finding-detail-content")

    def update_finding(self, finding) -> None:
        """Update detail panel with finding"""
        self._current_finding = finding

        content_widget = self.query_one("#finding-detail-content", Static)

        if not finding:
            content_widget.update("[dim]Select a finding to view details[/dim]")
            return

        # Build detail text
        lines = []
        lines.append(f"[bold]{finding.name}[/bold]")
        lines.append("")

        # Severity and confidence
        severity_colored = colorize_severity(finding.severity, finding.severity)
        lines.append(f"Severity: {severity_colored}")

        if hasattr(finding, 'confidence'):
            lines.append(f"Confidence: {finding.confidence}")

        lines.append("")

        # Host information
        if hasattr(finding, 'host') and finding.host:
            lines.append(f"[bold]Host:[/bold] {finding.host}")

        if hasattr(finding, 'netloc') and finding.netloc:
            lines.append(f"[bold]Location:[/bold] {finding.netloc}")

        if hasattr(finding, 'url') and finding.url:
            lines.append(f"[bold]URL:[/bold] {finding.url}")

        lines.append("")

        # Description
        if hasattr(finding, 'description') and finding.description:
            lines.append("[bold]Description:[/bold]")
            lines.append(finding.description)
            lines.append("")

        # CVEs
        if hasattr(finding, 'cves') and finding.cves:
            lines.append("[bold]CVEs:[/bold]")
            for cve in finding.cves:
                lines.append(f"  • {cve}")
            lines.append("")

        # Timestamps
        lines.append(f"Last Seen: {format_timestamp(finding.modified)}")
        if hasattr(finding, 'created'):
            lines.append(f"First Seen: {format_timestamp(finding.created)}")

        content_widget.update("\n".join(lines))

    def clear(self) -> None:
        """Clear the detail panel"""
        self.update_finding(None)
