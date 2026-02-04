"""
Main Textual application for BBOT Server TUI
"""

from typing import Iterable

from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.screen import Screen
from textual.theme import Theme
from textual.widgets import Header as TextualHeader, Footer, TabbedContent, TabPane


# BBOT Dark Theme - uses Textual's design system
# Custom colors (severity, status) are defined in styles.tcss as CSS variables
BBOT_DARK_THEME = Theme(
    name="bbot-dark",
    primary="#FF8400",  # BBOT signature orange
    secondary="#808080",  # Grey
    accent="#ffa62b",  # Lighter orange for accents
    foreground="#e0e0e0",  # Light text
    background="#000000",  # True black background
    surface="#121212",  # Widget backgrounds (very dark)
    panel="#1a1a1a",  # Panel backgrounds (slightly lighter)
    warning="#ffa62b",  # Orange-yellow warnings
    error="#f44336",  # Red errors
    success="#4caf50",  # Bright green (readable on dark)
    dark=True,
)

# BBOT Light Theme - light mode variant
BBOT_LIGHT_THEME = Theme(
    name="bbot-light",
    primary="#FF8400",  # BBOT signature orange
    secondary="#606060",  # Darker grey for light mode
    accent="#e67600",  # Darker orange for accents on light
    foreground="#1a1a1a",  # Dark text
    background="#ffffff",  # White background
    surface="#f5f5f5",  # Widget backgrounds (light grey)
    panel="#eeeeee",  # Panel backgrounds
    warning="#e67600",  # Darker orange warnings
    error="#d32f2f",  # Darker red errors
    success="#388e3c",  # Darker green (readable on light)
    dark=False,
)


from bbot_server.cli.tui.screens.dashboard import DashboardScreen
from bbot_server.cli.tui.screens.scans import ScansScreen
from bbot_server.cli.tui.screens.assets import AssetsScreen
from bbot_server.cli.tui.screens.findings import FindingsScreen
from bbot_server.cli.tui.screens.events import EventsScreen
from bbot_server.cli.tui.screens.technologies import TechnologiesScreen
from bbot_server.cli.tui.screens.targets import TargetsScreen
from bbot_server.cli.tui.screens.activity import ActivityScreen


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
        Binding("e", "show_events", "Events"),
        Binding("t", "show_technologies", "Technologies"),
        Binding("r", "show_targets", "Targets"),
        Binding("v", "show_activity", "Activity"),
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

        # TUI settings
        self.items_per_page = config.cli.tui_page_size

        # Services will be initialized after app starts
        self.data_service = None
        self.websocket_service = None
        self.state_service = None

        # Store screen instances
        self.dashboard_screen = None
        self.scans_screen = None
        self.assets_screen = None
        self.findings_screen = None
        self.events_screen = None
        self.technologies_screen = None
        self.targets_screen = None
        self.activity_screen = None

    def compose(self) -> ComposeResult:
        """Create child widgets for the app"""
        yield TextualHeader()

        # Create tabbed interface
        with TabbedContent(initial="tab-dashboard", id="main-tabs"):
            with TabPane("Dashboard", id="tab-dashboard"):
                self.dashboard_screen = DashboardScreen(self)
                yield self.dashboard_screen

            with TabPane("Scans", id="tab-scans"):
                self.scans_screen = ScansScreen(self)
                yield self.scans_screen

            with TabPane("Assets", id="tab-assets"):
                self.assets_screen = AssetsScreen(self)
                yield self.assets_screen

            with TabPane("Findings", id="tab-findings"):
                self.findings_screen = FindingsScreen(self)
                yield self.findings_screen

            with TabPane("Events", id="tab-events"):
                self.events_screen = EventsScreen(self)
                yield self.events_screen

            with TabPane("Technologies", id="tab-technologies"):
                self.technologies_screen = TechnologiesScreen(self)
                yield self.technologies_screen

            with TabPane("Targets", id="tab-targets"):
                self.targets_screen = TargetsScreen(self)
                yield self.targets_screen

            with TabPane("Activity", id="tab-activity"):
                self.activity_screen = ActivityScreen(self)
                yield self.activity_screen

        yield Footer()

    def on_mount(self) -> None:
        """Called when app is mounted - initialize services"""
        import logging
        from logging.handlers import RotatingFileHandler
        from pathlib import Path
        from bbot_server.cli.tui.services.data_service import DataService
        from bbot_server.cli.tui.services.websocket_service import WebSocketService
        from bbot_server.cli.tui.services.state_service import StateService

        # Register and apply the BBOT themes
        self.register_theme(BBOT_DARK_THEME)
        self.register_theme(BBOT_LIGHT_THEME)
        self.theme = "bbot-dark"

        # Filter to suppress "taking a while" warnings from HTTP client
        class SlowRequestFilter(logging.Filter):
            def filter(self, record):
                # Suppress "taking a while" warnings - these are informational
                if "taking a while" in record.getMessage():
                    return False
                return True

        # Setup file logging with rotation
        log_dir = Path.home() / ".bbot_server"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "tui.log"
        # 10MB max size, keep 1 backup (2 files total)
        file_handler = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=1)
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)

        # Add handler to root logger and TUI-specific loggers
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)
        root_logger.setLevel(logging.INFO)

        # Create filter instance
        slow_filter = SlowRequestFilter()

        # Add filter to suppress slow request warnings in TUI notifications
        # Apply to root logger
        root_logger.addFilter(slow_filter)

        # Also apply filter to all existing handlers (including Textual's)
        for handler in root_logger.handlers:
            handler.addFilter(slow_filter)

        # Apply to specific HTTP client logger
        http_logger = logging.getLogger("bbot_server.interfaces.http")
        http_logger.addFilter(slow_filter)
        for handler in http_logger.handlers:
            handler.addFilter(slow_filter)

        self.log.info(f"TUI logging to: {log_file}")

        # Initialize services
        self.data_service = DataService(self.bbot_server)
        self.websocket_service = WebSocketService(self.bbot_server)
        self.state_service = StateService()

        # Trigger initial refresh on all screens now that services are ready
        # Using call_later to ensure widgets are fully mounted
        self.call_later(self._initial_refresh)

    async def _initial_refresh(self) -> None:
        """Trigger initial data load for the dashboard (initial tab)"""
        # Load only the dashboard (initial tab)
        if self.dashboard_screen:
            await self.dashboard_screen.load_initial_data()

    def on_tabbed_content_tab_activated(self, event) -> None:
        """Handle tab changes - lazy load data on first visit"""
        # Get the TabbedContent widget and find which pane is active
        tabs = self.query_one("#main-tabs", TabbedContent)
        active_pane_id = tabs.active

        # Map pane IDs to screens
        tab_to_screen = {
            "tab-dashboard": self.dashboard_screen,
            "tab-scans": self.scans_screen,
            "tab-assets": self.assets_screen,
            "tab-findings": self.findings_screen,
            "tab-events": self.events_screen,
            "tab-technologies": self.technologies_screen,
            "tab-targets": self.targets_screen,
            "tab-activity": self.activity_screen,
        }

        # Get the screen for this tab and trigger lazy load
        screen = tab_to_screen.get(active_pane_id)
        if screen and hasattr(screen, "load_initial_data"):
            self.run_worker(screen.load_initial_data(), exclusive=True)

    async def action_quit(self) -> None:
        """Override quit to ensure cleanup"""
        # Stop ALL screen refresh timers
        screens_with_timers = [
            self.dashboard_screen,
            self.scans_screen,
            self.assets_screen,
            self.findings_screen,
            self.events_screen,
            self.technologies_screen,
            self.targets_screen,
        ]

        for screen in screens_with_timers:
            if screen and hasattr(screen, "_refresh_timer") and screen._refresh_timer:
                screen._refresh_timer.stop()

        # Stop activity streaming and its timer
        if self.activity_screen:
            if hasattr(self.activity_screen, "_start_timer") and self.activity_screen._start_timer:
                self.activity_screen._start_timer.stop()
            await self.activity_screen.stop_streaming()

        # Shutdown WebSocket service (properly closes async client)
        if self.websocket_service:
            await self.websocket_service.shutdown()

        # Now quit normally - clean exit!
        self.exit()

    def action_show_dashboard(self) -> None:
        """Show the dashboard tab"""
        tabs = self.query_one(TabbedContent)
        tabs.active = "tab-dashboard"

    def action_show_scans(self) -> None:
        """Show the scans tab"""
        tabs = self.query_one(TabbedContent)
        tabs.active = "tab-scans"

    def action_show_assets(self) -> None:
        """Show the assets tab"""
        tabs = self.query_one(TabbedContent)
        tabs.active = "tab-assets"

    def action_show_findings(self) -> None:
        """Show the findings tab"""
        tabs = self.query_one(TabbedContent)
        tabs.active = "tab-findings"

    def action_show_events(self) -> None:
        """Show the events tab"""
        tabs = self.query_one(TabbedContent)
        tabs.active = "tab-events"

    def action_show_technologies(self) -> None:
        """Show the technologies tab"""
        tabs = self.query_one(TabbedContent)
        tabs.active = "tab-technologies"

    def action_show_targets(self) -> None:
        """Show the targets tab"""
        tabs = self.query_one(TabbedContent)
        tabs.active = "tab-targets"

    def action_show_activity(self) -> None:
        """Show the activity tab"""
        tabs = self.query_one(TabbedContent)
        tabs.active = "tab-activity"

    def action_show_help(self) -> None:
        """Show help modal with keyboard shortcuts"""
        self.notify(
            "Help: d=Dashboard s=Scans a=Assets f=Findings e=Events t=Technologies r=Targets v=Activity q=Quit"
        )

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        """Add BBOT theme shortcuts to the system menu"""
        yield from super().get_system_commands(screen)
        yield SystemCommand("BBOT Dark Theme", "Switch to BBOT dark theme", self.action_theme_bbot_dark)
        yield SystemCommand("BBOT Light Theme", "Switch to BBOT light theme", self.action_theme_bbot_light)

    def action_theme_bbot_dark(self) -> None:
        """Switch to BBOT dark theme"""
        self.theme = "bbot-dark"

    def action_theme_bbot_light(self) -> None:
        """Switch to BBOT light theme"""
        self.theme = "bbot-light"
