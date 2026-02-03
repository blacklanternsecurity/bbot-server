"""
Main Textual application for BBOT Server TUI
"""
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header as TextualHeader, Footer

from bbot_server.cli.tui.screens.dashboard import DashboardScreen
from bbot_server.cli.tui.screens.scans import ScansScreen
from bbot_server.cli.tui.screens.assets import AssetsScreen
from bbot_server.cli.tui.screens.findings import FindingsScreen
from bbot_server.cli.tui.screens.activity import ActivityScreen
from bbot_server.cli.tui.screens.agents import AgentsScreen


class BBOTServerTUI(App):
    """
    Main Textual TUI Application for BBOT Server

    Provides a full-featured terminal user interface for monitoring and managing
    BBOT security scans, assets, findings, and agents with real-time updates.
    """

    TITLE = "BBOT Server"
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("d", "show_dashboard", "Dashboard"),
        Binding("s", "show_scans", "Scans"),
        Binding("a", "show_assets", "Assets"),
        Binding("f", "show_findings", "Findings"),
        Binding("v", "show_activity", "Activity"),
        Binding("g", "show_agents", "Agents"),
        Binding("question_mark", "show_help", "Help"),
    ]

    def __init__(self, bbot_server, config):
        """
        Initialize the TUI application

        Args:
            bbot_server: BBOTServer HTTP client instance
            config: BBOT server configuration
        """
        super().__init__()
        self.bbot_server = bbot_server
        self.config = config

        # Services will be initialized after app starts
        self.data_service = None
        self.websocket_service = None
        self.state_service = None

    def compose(self) -> ComposeResult:
        """Create child widgets for the app"""
        yield TextualHeader()
        yield Footer()

    def on_mount(self) -> None:
        """Called when app is mounted - initialize services"""
        from bbot_server.cli.tui.services.data_service import DataService
        from bbot_server.cli.tui.services.websocket_service import WebSocketService
        from bbot_server.cli.tui.services.state_service import StateService

        # Initialize services
        self.data_service = DataService(self.bbot_server)
        self.websocket_service = WebSocketService(self.bbot_server)
        self.state_service = StateService()

        # Install screens
        self.install_screen(DashboardScreen(self), name="dashboard")
        self.install_screen(ScansScreen(self), name="scans")
        self.install_screen(AssetsScreen(self), name="assets")
        self.install_screen(FindingsScreen(self), name="findings")
        self.install_screen(ActivityScreen(self), name="activity")
        self.install_screen(AgentsScreen(self), name="agents")

        # Show dashboard by default
        self.push_screen("dashboard")

    def action_show_dashboard(self) -> None:
        """Show the dashboard screen"""
        self.push_screen("dashboard")

    def action_show_scans(self) -> None:
        """Show the scans screen"""
        self.push_screen("scans")

    def action_show_assets(self) -> None:
        """Show the assets screen"""
        self.push_screen("assets")

    def action_show_findings(self) -> None:
        """Show the findings screen"""
        self.push_screen("findings")

    def action_show_activity(self) -> None:
        """Show the activity screen"""
        self.push_screen("activity")

    def action_show_agents(self) -> None:
        """Show the agents screen"""
        self.push_screen("agents")

    def action_show_help(self) -> None:
        """Show help modal with keyboard shortcuts"""
        # Will implement in Phase 9
        self.notify("Help: d=Dashboard s=Scans a=Assets f=Findings v=Activity g=Agents q=Quit")
