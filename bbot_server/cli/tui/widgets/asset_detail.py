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
            asset: Asset model or None to clear
        """
        self._current_asset = asset

        content_widget = self.query_one("#asset-detail-content", Static)

        if not asset:
            content_widget.update("[dim]Select an asset to view details[/dim]")
            return

        # Build detail text
        lines = []
        lines.append(f"[bold]{asset.host}[/bold]")
        lines.append("")

        # Open Ports
        if hasattr(asset, 'open_ports') and asset.open_ports:
            lines.append("[bold]Open Ports:[/bold]")
            ports_str = format_list(sorted([str(p) for p in asset.open_ports]), max_items=10)
            lines.append(f"  {ports_str}")
            lines.append("")

        # Technologies
        if hasattr(asset, 'technologies') and asset.technologies:
            lines.append("[bold]Technologies:[/bold]")
            techs_str = format_list(sorted(asset.technologies), max_items=10)
            lines.append(f"  {techs_str}")
            lines.append("")

        # Cloud Providers
        if hasattr(asset, 'cloud') and asset.cloud:
            lines.append("[bold]Cloud Providers:[/bold]")
            cloud_str = format_list(sorted(asset.cloud), max_items=5)
            lines.append(f"  {cloud_str}")
            lines.append("")

        # Findings
        if hasattr(asset, 'findings') and asset.findings:
            lines.append(f"[bold]Findings:[/bold] {len(asset.findings)}")
            lines.append("")

        # Scope
        if hasattr(asset, 'scope') and asset.scope:
            lines.append(f"[bold]In Scope:[/bold] {len(asset.scope)} target(s)")
            lines.append("")

        # Timestamps
        lines.append(f"Created: {format_timestamp(asset.created)}")
        lines.append(f"Modified: {format_timestamp(asset.modified)}")

        # Update the content
        content_widget.update("\n".join(lines))

    def clear(self) -> None:
        """Clear the detail panel"""
        self.update_asset(None)
