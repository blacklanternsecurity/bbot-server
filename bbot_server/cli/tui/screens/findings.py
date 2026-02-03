"""
Findings screen for BBOT Server TUI
"""
from textual.app import ComposeResult
# Removed Screen import
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static, Button
from textual.reactive import reactive

from bbot_server.cli.tui.widgets.finding_table import FindingTable
from bbot_server.cli.tui.widgets.finding_detail import FindingDetail
from bbot_server.cli.tui.widgets.filter_bar import FilterBar


class FindingsScreen(Container):
    """Findings viewer screen with severity filtering"""


    filter_text = reactive("")
    min_severity = reactive(1)  # 1=INFO, 5=CRITICAL

    def __init__(self, app):
        super().__init__()
        self.bbot_app = app
        self._refresh_timer = None
        self._has_loaded = False

    def compose(self) -> ComposeResult:
        """Create child widgets"""
        with Container(id="findings-container"):
            # Filter controls
            with Horizontal(id="finding-controls"):
                yield FilterBar(placeholder="Search by name, host, or description...", id="finding-filter")
                yield Static("Severity: ALL", id="severity-filter")
                yield Button("Refresh", id="refresh-btn", variant="primary")

            # Status bar
            yield Static("Loading findings...", id="findings-status")

            # Main content
            with Horizontal(id="findings-content"):
                with Vertical(id="findings-table-container"):
                    yield FindingTable(id="finding-table")

                with Vertical(id="finding-detail-container"):
                    yield Static("[bold]Finding Details[/bold]", id="detail-header")
                    yield FindingDetail(id="finding-detail")


    async def on_mount(self) -> None:
        """Called when screen is mounted"""
        # Start periodic refresh (paused until first load)
        self._refresh_timer = self.set_interval(10.0, self.refresh_findings, pause=True)

    async def load_initial_data(self) -> None:
        """Load data on first visit to this tab"""
        if self._has_loaded:
            return

        self._has_loaded = True
        await self.refresh_findings(show_loading=True)

        # Resume periodic refresh
        if self._refresh_timer:
            self._refresh_timer.resume()

    async def on_unmount(self) -> None:
        """Called when screen is unmounted"""
        if self._refresh_timer:
            self._refresh_timer.stop()

    async def refresh_findings(self, show_loading: bool = False) -> None:
        """Fetch and display all findings from server

        Args:
            show_loading: If True, show "Loading..." status message (for manual refreshes)
        """
        # Check if services are initialized
        if not self.bbot_app.data_service:
            return

        try:
            status = self.query_one("#findings-status", Static)
            # Only show loading message on initial load or manual refresh
            if show_loading:
                status.update("[cyan]Loading findings...[/cyan]")

            # Fetch all findings
            findings = await self.bbot_app.data_service.list_findings()

            # Apply client-side filters
            from bbot_server.cli.tui.utils.colors import get_severity_score

            # Apply severity filter
            if self.min_severity > 1:
                findings = [
                    f for f in findings
                    if get_severity_score(getattr(f, 'severity', 'INFO')) >= self.min_severity
                ]

            # Apply text search filter
            if self.filter_text:
                filter_lower = self.filter_text.lower()
                findings = [
                    f for f in findings
                    if filter_lower in getattr(f, 'name', '').lower()
                    or filter_lower in getattr(f, 'host', '').lower()
                    or filter_lower in getattr(f, 'description', '').lower()
                ]

            # Update table with all filtered findings
            table = self.query_one("#finding-table", FindingTable)
            table.update_findings(findings)

            # Update status
            if findings:
                if self.filter_text or self.min_severity > 1:
                    status.update(f"[green]Showing {len(findings)} filtered findings[/green]")
                else:
                    status.update(f"[green]Showing {len(findings)} findings[/green]")
            else:
                status.update("[yellow]No findings found[/yellow]")

        except Exception as e:
            # Show error
            status = self.query_one("#findings-status", Static)
            status.update(f"[red]Error loading findings: {e}[/red]")

    def on_data_table_row_highlighted(self, event) -> None:
        """Handle row selection"""
        # Only handle events from the finding table
        if event.data_table.id != "finding-table":
            return

        table = self.query_one("#finding-table", FindingTable)
        finding = table.get_selected_finding()

        # Update detail panel
        detail = self.query_one("#finding-detail", FindingDetail)
        detail.update_finding(finding)

    def on_filter_bar_filter_changed(self, event: FilterBar.FilterChanged) -> None:
        """Handle filter text changes"""
        self.filter_text = event.filter_text
        # Trigger refresh (show loading since user-initiated)
        self.run_worker(self.refresh_findings(show_loading=True))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "refresh-btn":
            await self.action_refresh()

    async def action_refresh(self) -> None:
        """Refresh findings"""
        await self.refresh_findings(show_loading=True)
        self.notify("Findings refreshed", timeout=2)

    def action_focus_filter(self) -> None:
        """Focus the filter input"""
        filter_bar = self.query_one("#finding-filter", FilterBar)
        filter_bar.focus()

    def action_clear_filter(self) -> None:
        """Clear the filter"""
        filter_bar = self.query_one("#finding-filter", FilterBar)
        filter_bar.clear_filter()
        self.filter_text = ""

    def action_filter_info(self) -> None:
        """Show INFO and above"""
        self.min_severity = 1
        self._update_severity_label()
        self.run_worker(self.refresh_findings())

    def action_filter_low(self) -> None:
        """Show LOW and above"""
        self.min_severity = 2
        self._update_severity_label()
        self.run_worker(self.refresh_findings())

    def action_filter_medium(self) -> None:
        """Show MEDIUM and above"""
        self.min_severity = 3
        self._update_severity_label()
        self.run_worker(self.refresh_findings())

    def action_filter_high(self) -> None:
        """Show HIGH and above"""
        self.min_severity = 4
        self._update_severity_label()
        self.run_worker(self.refresh_findings())

    def action_filter_critical(self) -> None:
        """Show CRITICAL only"""
        self.min_severity = 5
        self._update_severity_label()
        self.run_worker(self.refresh_findings())

    def _update_severity_label(self) -> None:
        """Update the severity filter label"""
        severity_names = {1: "ALL", 2: "LOW+", 3: "MEDIUM+", 4: "HIGH+", 5: "CRITICAL"}
        label = severity_names.get(self.min_severity, "ALL")
        severity_widget = self.query_one("#severity-filter", Static)
        severity_widget.update(f"Severity: {label}")
