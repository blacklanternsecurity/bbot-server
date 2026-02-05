"""
Asset detail panel widget for BBOT Server TUI
"""

from textual.widgets import Static
from textual.containers import Container

from bbot_server.cli.tui.utils.formatters import format_timestamp, format_list


class AssetDetail(Container):
    """
    Widget for displaying detailed information about a selected asset
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._current_asset = None

    def compose(self):
        """Create child widgets"""
        yield Static("", id="asset-detail-content")

    def update_asset(self, asset) -> None:
        """
        Update the detail panel with asset information

        Args:
            asset: Asset dict or None to clear
        """
        self._current_asset = asset

        content_widget = self.query_one("#asset-detail-content", Static)

        if not asset:
            content_widget.update("[dim]Select an asset to view details[/dim]")
            return

        # Build detail text
        lines = []
        host = asset.get("host", "unknown")
        lines.append(f"[bold]{host}[/bold]")
        lines.append("")

        # Open Ports
        open_ports = asset.get("open_ports")
        if open_ports:
            lines.append("[bold]Open Ports:[/bold]")
            ports_str = format_list(sorted([str(p) for p in open_ports]), max_items=10)
            lines.append(f"  {ports_str}")
            lines.append("")

        # Technologies
        technologies = asset.get("technologies")
        if technologies:
            lines.append("[bold]Technologies:[/bold]")
            techs_str = format_list(sorted(technologies), max_items=10)
            lines.append(f"  {techs_str}")
            lines.append("")

        # Cloud Providers
        cloud = asset.get("cloud")
        if cloud:
            lines.append("[bold]Cloud Providers:[/bold]")
            cloud_str = format_list(sorted(cloud), max_items=5)
            lines.append(f"  {cloud_str}")
            lines.append("")

        # Findings
        findings = asset.get("findings")
        if findings:
            lines.append(f"[bold]Findings:[/bold] {len(findings)}")
            lines.append("")

        # Scope
        scope = asset.get("scope")
        if scope:
            lines.append(f"[bold]In Scope:[/bold] {len(scope)} target(s)")
            lines.append("")

        # Timestamps
        created = asset.get("created")
        modified = asset.get("modified")
        if created:
            lines.append(f"Created: {format_timestamp(created)}")
        if modified:
            lines.append(f"Modified: {format_timestamp(modified)}")

        # Update the content
        content_widget.update("\n".join(lines))

    def clear(self) -> None:
        """Clear the detail panel"""
        self.update_asset(None)
