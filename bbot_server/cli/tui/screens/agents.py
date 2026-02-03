"""
Agents screen for BBOT Server TUI
"""
from textual.app import ComposeResult
# Removed Screen import
from textual.containers import Container, Horizontal
from textual.widgets import Static, Button, DataTable

from bbot_server.cli.tui.utils.formatters import format_timestamp_short


class AgentsScreen(Container):
    """Agent management screen"""


    def __init__(self, app):
        super().__init__()
        self.bbot_app = app
        self._refresh_timer = None
        self._has_loaded = False

    def compose(self) -> ComposeResult:
        """Create child widgets"""
        with Container(id="agents-container"):
            # Controls
            with Horizontal(id="agent-controls"):
                yield Static("[bold]Agents[/bold]", id="agents-title")
                yield Button("New Agent", id="new-agent-btn", variant="success")
                yield Button("Refresh", id="refresh-btn", variant="primary")

            # Status
            yield Static("Loading agents...", id="agents-status")

            # Agent list
            yield DataTable(id="agent-table")


    async def on_mount(self) -> None:
        """Called when screen is mounted"""
        # Setup table
        table = self.query_one("#agent-table", DataTable)
        table.add_columns("ID", "Status", "Last Seen")
        table.cursor_type = "row"
        table.zebra_stripes = True

        # Start periodic refresh (paused until first load)
        self._refresh_timer = self.set_interval(5.0, self.refresh_agents, pause=True)

    async def load_initial_data(self) -> None:
        """Load data on first visit to this tab"""
        if self._has_loaded:
            return

        self._has_loaded = True
        await self.refresh_agents()

        # Resume periodic refresh
        if self._refresh_timer:
            self._refresh_timer.resume()

    async def on_unmount(self) -> None:
        """Called when screen is unmounted"""
        if self._refresh_timer:
            self._refresh_timer.stop()

    async def refresh_agents(self) -> None:
        """Fetch and display agents"""
        # Check if services are initialized
        if not self.bbot_app.data_service:
            return

        try:
            status = self.query_one("#agents-status", Static)
            status.update("[cyan]Loading agents...[/cyan]")

            # Fetch agents
            agents = await self.bbot_app.data_service.get_agents()

            # Update table
            table = self.query_one("#agent-table", DataTable)
            table.clear()

            for agent in agents:
                agent_id = str(agent.id) if hasattr(agent, 'id') else "-"
                agent_status = agent.status if hasattr(agent, 'status') else "UNKNOWN"
                last_seen = format_timestamp_short(agent.last_seen) if hasattr(agent, 'last_seen') and agent.last_seen else "-"

                table.add_row(agent_id, agent_status, last_seen)

            # Update status
            if agents:
                status.update(f"[green]Loaded {len(agents)} agents[/green]")
            else:
                status.update("[yellow]No agents found[/yellow]")

        except Exception as e:
            status = self.query_one("#agents-status", Static)
            status.update(f"[red]Error loading agents: {e}[/red]")

    def on_data_table_row_selected(self, event) -> None:
        """Handle Enter key on agent table - do nothing for now"""
        # Prevent accidental agent creation when pressing Enter
        pass

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "refresh-btn":
            await self.action_refresh()
        elif event.button.id == "new-agent-btn":
            await self.action_create_agent()

    async def action_refresh(self) -> None:
        """Refresh agents"""
        await self.refresh_agents()
        self.notify("Agents refreshed", timeout=2)

    async def action_create_agent(self) -> None:
        """Create a new agent"""
        try:
            # Generate a unique name using timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            agent_name = f"agent-{timestamp}"

            agent = await self.bbot_app.data_service.create_agent(name=agent_name)
            if agent:
                self.notify(f"Created agent: {agent_name}", timeout=3)
                await self.refresh_agents()
            else:
                self.notify("Failed to create agent", severity="error", timeout=3)
        except Exception as e:
            self.notify(f"Error creating agent: {e}", severity="error", timeout=5)
