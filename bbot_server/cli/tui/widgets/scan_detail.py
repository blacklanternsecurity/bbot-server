"""
Scan detail panel widget for BBOT Server TUI
"""
from textual.widgets import Static
from textual.containers import Container

from bbot_server.cli.tui.utils.formatters import (
    format_timestamp,
    format_duration,
    format_number,
)
from bbot_server.cli.tui.utils.colors import colorize_status


class ScanDetail(Container):
    """
    Widget for displaying detailed information about a selected scan

    Shows comprehensive scan information including status, timing,
    configuration, and statistics.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._current_scan = None

    def compose(self):
        """Create child widgets"""
        yield Static("", id="scan-detail-content")

    def update_scan(self, scan) -> None:
        """
        Update the detail panel with scan information

        Args:
            scan: Scan model or None to clear
        """
        self._current_scan = scan

        content_widget = self.query_one("#scan-detail-content", Static)

        if not scan:
            content_widget.update("[dim]Select a scan to view details[/dim]")
            return

        # Build detail text with Rich markup
        lines = []
        lines.append(f"[bold]{scan.name or scan.id}[/bold]")
        lines.append("")

        # Status
        status_colored = colorize_status(scan.status, scan.status)
        lines.append(f"Status: {status_colored}")

        # Timing information
        if scan.started_at:
            lines.append(f"Started: {format_timestamp(scan.started_at)}")
        if scan.finished_at:
            lines.append(f"Finished: {format_timestamp(scan.finished_at)}")
        if scan.duration_seconds:
            lines.append(f"Duration: {format_duration(scan.duration_seconds)}")

        lines.append("")

        # Target information
        if hasattr(scan, 'target') and scan.target:
            lines.append("[bold]Target:[/bold]")
            lines.append(f"  Name: {scan.target.name}")

            if hasattr(scan.target, 'target') and scan.target.target:
                target_list = scan.target.target
                if isinstance(target_list, list) and target_list:
                    lines.append(f"  Targets: {', '.join(target_list[:5])}")
                    if len(target_list) > 5:
                        lines.append(f"           (+{len(target_list) - 5} more)")

            if hasattr(scan.target, 'seeds') and scan.target.seeds:
                seed_list = scan.target.seeds
                if isinstance(seed_list, list) and seed_list:
                    lines.append(f"  Seeds: {', '.join(seed_list[:5])}")
                    if len(seed_list) > 5:
                        lines.append(f"         (+{len(seed_list) - 5} more)")

            lines.append("")

        # Preset information
        if hasattr(scan, 'preset') and scan.preset:
            lines.append("[bold]Preset:[/bold]")
            lines.append(f"  Name: {scan.preset.name}")

            # Show some preset details if available
            if hasattr(scan.preset, 'preset') and isinstance(scan.preset.preset, dict):
                preset_config = scan.preset.preset

                # Show modules if available
                if 'modules' in preset_config:
                    modules = preset_config['modules']
                    if isinstance(modules, list) and modules:
                        lines.append(f"  Modules: {', '.join(modules[:5])}")
                        if len(modules) > 5:
                            lines.append(f"           (+{len(modules) - 5} more)")

            lines.append("")

        # Agent information
        if scan.agent_id:
            lines.append(f"Agent: {scan.agent_id}")
        else:
            lines.append("Agent: [dim]Not assigned[/dim]")

        lines.append("")

        # Scan ID
        lines.append(f"[dim]ID: {scan.id}[/dim]")

        # Update the content
        content_widget.update("\n".join(lines))

    def clear(self) -> None:
        """Clear the detail panel"""
        self.update_scan(None)
