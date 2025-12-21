"""
Dashboard screen for BBOT Server TUI
"""
from textual.app import ComposeResult
# Removed Screen import
from textual.containers import Container, Horizontal, Vertical, Grid
from textual.widgets import Static, Button, Footer, DataTable
from textual.binding import Binding
from textual.css.query import NoMatches

from bbot_server.cli.tui.utils.formatters import format_number, format_timestamp_short
from bbot_server.cli.tui.utils.colors import get_severity_color, colorize_severity


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
            with Horizontal(id="dashboard-header"):
                yield Static("[bold]BBOT Server Dashboard[/bold]", id="dashboard-title")
                yield Button("Refresh", id="refresh-btn", variant="primary")

            # Stats cards
            with Grid(id="stats-grid"):
                yield Container(
                    Static("0", id="stat-scans-value", classes="stat-value"),
                    Static("Total Scans", classes="stat-label"),
                    id="stat-scans",
                    classes="stat-card"
                )
                yield Container(
                    Static("0", id="stat-active-value", classes="stat-value"),
                    Static("Active Scans", classes="stat-label"),
                    id="stat-active",
                    classes="stat-card"
                )
                yield Container(
                    Static("0", id="stat-assets-value", classes="stat-value"),
                    Static("Assets", classes="stat-label"),
                    id="stat-assets",
                    classes="stat-card"
                )
                yield Container(
                    Static("0", id="stat-findings-value", classes="stat-value"),
                    Static("Findings", classes="stat-label"),
                    id="stat-findings",
                    classes="stat-card"
                )
                yield Container(
                    Static("0", id="stat-agents-value", classes="stat-value"),
                    Static("Agents", classes="stat-label"),
                    id="stat-agents",
                    classes="stat-card"
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
            # Fetch stats
            stats = await self.bbot_app.data_service.get_stats()

            # Update stat cards
            self.query_one("#stat-scans-value", Static).update(
                format_number(stats.get('scan_count', 0))
            )
            self.query_one("#stat-active-value", Static).update(
                format_number(stats.get('active_scan_count', 0))
            )
            self.query_one("#stat-assets-value", Static).update(
                format_number(stats.get('asset_count', 0))
            )
            self.query_one("#stat-findings-value", Static).update(
                format_number(stats.get('finding_count', 0))
            )
            self.query_one("#stat-agents-value", Static).update(
                format_number(stats.get('agent_count', 0))
            )

            # Update recent findings
            await self.update_recent_findings()

            # Update recent scans
            await self.update_recent_scans()

            # Update status
            status = self.query_one("#dashboard-status", Static)
            status.update("[green]● Connected[/green]")

        except Exception as e:
            # Show error
            status = self.query_one("#dashboard-status", Static)
            status.update(f"[red]● Error: {e}[/red]")

    async def update_recent_findings(self) -> None:
        """Update the recent findings table (sorted by severity)"""
        try:
            # Fetch recent findings (no severity filter, get more to sort)
            findings = await self.bbot_app.data_service.list_findings(limit=50)

            # Sort by severity (highest first), then by modified time (most recent first)
            # Note: findings are Pydantic models, use attribute access not dict access
            from bbot_server.cli.tui.utils.colors import get_severity_score
            findings_sorted = sorted(
                findings,
                key=lambda f: (-get_severity_score(f.severity if hasattr(f, 'severity') else 'INFO'),
                              -(f.modified if hasattr(f, 'modified') else 0))
            )

            # Take top 10 after sorting
            findings_sorted = findings_sorted[:10]

            # Update table
            table = self.query_one("#recent-findings-table", DataTable)
            table.clear()

            for finding in findings_sorted:
                # Get severity info (finding is a Pydantic model)
                severity_name = finding.severity if hasattr(finding, 'severity') else 'UNKNOWN'

                # Colorize severity
                severity_text = colorize_severity(severity_name, severity_name[:4].upper())

                # Get other fields
                name = finding.name if hasattr(finding, 'name') else 'Unknown'
                name = name[:30]  # Truncate long names

                host = finding.host if hasattr(finding, 'host') else '-'
                host = host[:25]  # Truncate long hosts

                # Format timestamp
                last_seen = finding.modified if hasattr(finding, 'modified') else None
                when = format_timestamp_short(last_seen) if last_seen else '-'

                table.add_row(severity_text, name, host, when)

            if not findings:
                table.add_row("-", "No recent findings", "-", "-")

        except Exception as e:
            # Log the error so we can see what went wrong
            import logging
            logging.error(f"Error updating recent findings: {e}")
            # Don't break the dashboard
            pass

    async def update_recent_scans(self) -> None:
        """Update the recent scans table"""
        try:
            # Fetch recent scans (last 10)
            scans = await self.bbot_app.data_service.get_scans()

            # Sort by created timestamp (most recent first)
            scans_sorted = sorted(
                scans,
                key=lambda s: s.created if hasattr(s, 'created') and s.created else '',
                reverse=True
            )[:10]

            # Update table
            table = self.query_one("#recent-scans-table", DataTable)
            table.clear()

            for scan in scans_sorted:
                # Get scan name or ID
                name = scan.name if hasattr(scan, 'name') and scan.name else str(scan.id)[:8]
                name = name[:20]  # Truncate long names

                # Get status with color
                status = scan.status if hasattr(scan, 'status') else 'UNKNOWN'
                if status == 'RUNNING':
                    status_text = f"[darkorange]{status}[/darkorange]"
                elif status == 'DONE':
                    status_text = f"[green]{status}[/green]"
                elif status == 'FAILED':
                    status_text = f"[red]{status}[/red]"
                else:
                    status_text = f"[grey]{status}[/grey]"

                # Get target
                target = scan.target.name if hasattr(scan, 'target') and hasattr(scan.target, 'name') else '-'
                target = target[:25]  # Truncate long targets

                # Format timestamp
                started = scan.created if hasattr(scan, 'created') else None
                when = format_timestamp_short(started) if started else '-'

                table.add_row(name, status_text, target, when)

            if not scans_sorted:
                table.add_row("-", "No recent scans", "-", "-")

        except Exception as e:
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
