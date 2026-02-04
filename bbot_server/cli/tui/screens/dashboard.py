"""
Dashboard screen for BBOT Server TUI
"""

from textual.app import ComposeResult

# Removed Screen import
from textual.containers import Container, Horizontal, Vertical, Grid
from textual.widgets import Static, Button, DataTable

from bbot_server.cli.tui.utils.formatters import format_number, format_timestamp_short
from bbot_server.cli.tui.utils.colors import colorize_severity, colorize_status, success_text, error_text


class DashboardScreen(Container):
    """Dashboard overview screen with stats and recent activity"""

    def __init__(self, app):
        super().__init__()
        self.bbot_app = app
        self._refresh_timer = None
        self._has_loaded = False

    def compose(self) -> ComposeResult:
        """Create child widgets"""
        with Container(id="dashboard-container"):
            # Title and refresh
            with Horizontal(id="dashboard-header", classes="controls-bar"):
                yield Static("[bold]BBOT Server Dashboard[/bold]", id="dashboard-title")
                yield Button("Refresh", id="refresh-btn", variant="primary")

            # Stats cards
            with Grid(id="stats-grid"):
                yield Container(
                    Static("0", id="stat-scans-value", classes="stat-value"),
                    Static("Total Scans", classes="stat-label"),
                    id="stat-scans",
                    classes="stat-card",
                )
                yield Container(
                    Static("0", id="stat-active-value", classes="stat-value"),
                    Static("Active Scans", classes="stat-label"),
                    id="stat-active",
                    classes="stat-card",
                )
                yield Container(
                    Static("0", id="stat-assets-value", classes="stat-value"),
                    Static("Assets", classes="stat-label"),
                    id="stat-assets",
                    classes="stat-card",
                )
                yield Container(
                    Static("0", id="stat-findings-value", classes="stat-value"),
                    Static("Findings", classes="stat-label"),
                    id="stat-findings",
                    classes="stat-card",
                )

            # Status message
            yield Static("Loading...", id="dashboard-status")

            # Two-column layout for lists
            with Horizontal(id="dashboard-lists"):
                # Recent findings sorted by severity
                with Vertical(id="findings-section"):
                    yield Static("[bold]Recent Findings (by Severity)[/bold]", classes="section-title")
                    findings_table = DataTable(id="recent-findings-table", show_cursor=False)
                    findings_table.add_columns("Severity", "Name", "Host", "When")
                    yield findings_table

                # Recent scans
                with Vertical(id="scans-section"):
                    yield Static("[bold]Recent Scans[/bold]", classes="section-title")
                    scans_table = DataTable(id="recent-scans-table", show_cursor=False)
                    scans_table.add_columns("Name", "Status", "Target", "Started")
                    yield scans_table

    async def on_mount(self) -> None:
        """Called when screen is mounted"""
        # Start periodic refresh (paused until first load)
        self._refresh_timer = self.set_interval(5.0, self.refresh_dashboard, pause=True)

    async def load_initial_data(self) -> None:
        """Load data on first visit to this tab"""
        if self._has_loaded:
            return

        self._has_loaded = True
        await self.refresh_dashboard()

        # Resume periodic refresh
        if self._refresh_timer:
            self._refresh_timer.resume()

    async def on_unmount(self) -> None:
        """Called when screen is unmounted"""
        if self._refresh_timer:
            self._refresh_timer.stop()

    async def refresh_dashboard(self) -> None:
        """Fetch and display dashboard stats"""
        # Check if services are initialized
        if not self.bbot_app.data_service:
            return

        try:
            # Fetch scans to count them
            scans = await self.bbot_app.data_service.get_scans()
            scan_count = len(scans)
            active_scan_count = sum(1 for scan in scans if hasattr(scan, "status") and scan.status == "RUNNING")

            # Get counts via paginated endpoints
            _, asset_count = await self.bbot_app.data_service.get_assets_paginated(limit=1)
            _, finding_count = await self.bbot_app.data_service.get_findings_paginated(limit=1)

            # Update stat cards
            self.query_one("#stat-scans-value", Static).update(format_number(scan_count))
            self.query_one("#stat-active-value", Static).update(format_number(active_scan_count))
            self.query_one("#stat-assets-value", Static).update(format_number(asset_count))
            self.query_one("#stat-findings-value", Static).update(format_number(finding_count))

            # Update recent findings
            await self.update_recent_findings()

            # Update recent scans
            await self.update_recent_scans()

            # Update status
            status = self.query_one("#dashboard-status", Static)
            status.update(success_text("● Connected"))

        except Exception as e:
            # Show error
            status = self.query_one("#dashboard-status", Static)
            status.update(error_text(f"● Error: {e}"))

    async def update_recent_findings(self) -> None:
        """Update the recent findings table (sorted by severity)"""
        try:
            # Fetch recent findings (no severity filter, get more to sort)
            findings, _ = await self.bbot_app.data_service.get_findings_paginated(limit=50)

            # Sort by severity (highest first), then by modified time (most recent first)
            from bbot_server.cli.tui.utils.colors import get_severity_score

            findings_sorted = sorted(
                findings,
                key=lambda f: (-get_severity_score(f.get("severity", "INFO")), -(f.get("modified", 0) or 0)),
            )

            # Take top 10 after sorting
            findings_sorted = findings_sorted[:10]

            # Update table
            table = self.query_one("#recent-findings-table", DataTable)
            table.clear()

            for finding in findings_sorted:
                severity_name = finding.get("severity", "UNKNOWN")
                severity_text = colorize_severity(severity_name, severity_name[:4].upper())

                name = finding.get("name", "Unknown") or "Unknown"
                name = name[:30]

                host = finding.get("host", "-") or "-"
                host = host[:25]

                last_seen = finding.get("modified")
                when = format_timestamp_short(last_seen) if last_seen else "-"

                table.add_row(severity_text, name, host, when)

            if not findings:
                table.add_row("-", "No recent findings", "-", "-")

        except Exception as e:
            import logging

            logging.error(f"Error updating recent findings: {e}")
            pass

    async def update_recent_scans(self) -> None:
        """Update the recent scans table"""
        try:
            # Fetch recent scans (last 10)
            scans = await self.bbot_app.data_service.get_scans()

            # Sort by created timestamp (most recent first)
            scans_sorted = sorted(
                scans, key=lambda s: s.created if hasattr(s, "created") and s.created else "", reverse=True
            )[:10]

            # Update table
            table = self.query_one("#recent-scans-table", DataTable)
            table.clear()

            for scan in scans_sorted:
                # Get scan name or ID
                name = scan.name if hasattr(scan, "name") and scan.name else str(scan.id)[:8]
                name = name[:20]  # Truncate long names

                # Get status with color
                status = scan.status if hasattr(scan, "status") else "UNKNOWN"
                status_text = colorize_status(status, status)

                # Get target
                target = scan.target.name if hasattr(scan, "target") and hasattr(scan.target, "name") else "-"
                target = target[:25]  # Truncate long targets

                # Format timestamp
                started = scan.created if hasattr(scan, "created") else None
                when = format_timestamp_short(started) if started else "-"

                table.add_row(name, status_text, target, when)

            if not scans_sorted:
                table.add_row("-", "No recent scans", "-", "-")

        except Exception:
            # Silent fail - don't break the dashboard
            pass

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "refresh-btn":
            await self.action_refresh()

    async def action_refresh(self) -> None:
        """Refresh dashboard"""
        await self.refresh_dashboard()
        self.notify("Dashboard refreshed", timeout=2)
