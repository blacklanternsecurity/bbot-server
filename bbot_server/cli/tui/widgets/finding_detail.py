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

        lines = []
        name = finding.get("name", "Unknown")
        lines.append(f"[bold]{name}[/bold]")
        lines.append("")

        severity = finding.get("severity", "INFO")
        severity_colored = colorize_severity(severity, severity)
        lines.append(f"Severity: {severity_colored}")

        confidence = finding.get("confidence")
        if confidence:
            lines.append(f"Confidence: {confidence}")

        lines.append("")

        host = finding.get("host")
        if host:
            lines.append(f"[bold]Host:[/bold] {host}")

        netloc = finding.get("netloc")
        if netloc:
            lines.append(f"[bold]Location:[/bold] {netloc}")

        url = finding.get("url")
        if url:
            lines.append(f"[bold]URL:[/bold] {url}")

        lines.append("")

        description = finding.get("description")
        if description:
            lines.append("[bold]Description:[/bold]")
            lines.append(description)
            lines.append("")

        cves = finding.get("cves")
        if cves:
            lines.append("[bold]CVEs:[/bold]")
            for cve in cves:
                lines.append(f"  • {cve}")
            lines.append("")

        modified = finding.get("modified")
        if modified:
            lines.append(f"Last Seen: {format_timestamp(modified)}")
        created = finding.get("created")
        if created:
            lines.append(f"First Seen: {format_timestamp(created)}")

        content_widget.update("\n".join(lines))

    def clear(self) -> None:
        """Clear the detail panel"""
        self.update_finding(None)
