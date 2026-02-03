"""
Targets screen for BBOT Server TUI
"""
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static, Button
from textual.reactive import reactive
from textual import work

from bbot_server.cli.tui.widgets.target_table import TargetTable
from bbot_server.cli.tui.widgets.target_detail import TargetDetail
from bbot_server.cli.tui.widgets.filter_bar import FilterBar
from bbot_server.cli.tui.widgets.paginated_table import PaginatedTableContainer
from bbot_server.cli.tui.screens.create_target_modal import TargetModal
from bbot_server.cli.tui.screens.confirm_modal import ConfirmModal


class TargetsScreen(Container):
    """Targets management screen"""

    filter_text = reactive("")

    def __init__(self, app):
        super().__init__()
        self.bbot_app = app
        self._refresh_timer = None
        self._has_loaded = False

    def compose(self) -> ComposeResult:
        """Create child widgets"""
        with Container(id="targets-container"):
            # Controls
            with Horizontal(id="target-controls"):
                yield FilterBar(placeholder="Filter by target name or description...", id="target-filter")
                yield Button("New Target", id="new-target-btn", variant="success")
                yield Button("Edit", id="edit-target-btn", variant="warning")
                yield Button("Delete", id="delete-target-btn", variant="error")
                yield Button("Refresh", id="refresh-btn", variant="primary")

            # Status bar
            yield Static("Loading targets...", id="targets-status")

            # Main content
            with Horizontal(id="targets-content"):
                with Vertical(id="targets-table-container"):
                    yield PaginatedTableContainer(
                        TargetTable(id="target-table"),
                        auto_page_size=True,
                        id="target-pagination"
                    )

                with Vertical(id="target-detail-container"):
                    yield Static("[bold]Target Details[/bold]", id="detail-header")
                    yield TargetDetail(id="target-detail")

    async def on_mount(self) -> None:
        """Called when screen is mounted"""
        # Start periodic refresh (paused until first load)
        self._refresh_timer = self.set_interval(30.0, self.refresh_targets, pause=True)

    async def load_initial_data(self) -> None:
        """Load data on first visit to this tab"""
        if self._has_loaded:
            return

        self._has_loaded = True
        await self.refresh_targets(show_loading=True)

        # Resume periodic refresh
        if self._refresh_timer:
            self._refresh_timer.resume()

    async def on_unmount(self) -> None:
        """Called when screen is unmounted"""
        if self._refresh_timer:
            self._refresh_timer.stop()

    async def refresh_targets(self, show_loading: bool = False) -> None:
        """Fetch and display targets from server with pagination

        Args:
            show_loading: If True, show "Loading..." status message (for manual refreshes)
        """
        # Check if services are initialized
        if not self.bbot_app.data_service:
            return

        try:
            status = self.query_one("#targets-status", Static)
            # Only show loading message on initial load or manual refresh
            if show_loading:
                status.update("[cyan]Loading targets...[/cyan]")

            # Get pagination parameters
            pagination = self.query_one("#target-pagination", PaginatedTableContainer)
            skip, limit = pagination.get_skip_limit()

            # Fetch targets with client-side pagination and filter
            filter_text = self.filter_text if self.filter_text else None
            targets, total = await self.bbot_app.data_service.get_targets_paginated(
                skip=skip, limit=limit, filter_text=filter_text
            )

            # Update pagination with total count
            pagination.total_items = total

            # Update table with current page of targets
            table = self.query_one("#target-table", TargetTable)
            table.update_targets(targets)

            # Update status (pagination widget shows page info, status shows filter info)
            if total > 0:
                if self.filter_text:
                    status.update(f"[green]Filtered: {total} targets match[/green]")
                else:
                    status.update(f"[green]{total} total targets[/green]")
            else:
                status.update("[yellow]No targets found[/yellow]")

        except Exception as e:
            # Show error
            status = self.query_one("#targets-status", Static)
            status.update(f"[red]Error loading targets: {e}[/red]")

    def on_data_table_row_highlighted(self, event) -> None:
        """Handle row selection"""
        # Only handle events from the target table
        if event.data_table.id != "target-table":
            return

        table = self.query_one("#target-table", TargetTable)
        selected_target = table.get_selected_target()

        # Update detail panel
        detail = self.query_one("#target-detail", TargetDetail)
        detail.update_target(selected_target)

    def on_filter_bar_filter_changed(self, event: FilterBar.FilterChanged) -> None:
        """Handle filter text changes"""
        self.filter_text = event.filter_text
        # Reset to first page when filter changes
        pagination = self.query_one("#target-pagination", PaginatedTableContainer)
        pagination.reset_to_first_page()
        # Trigger refresh (show loading since user-initiated)
        self.run_worker(self.refresh_targets(show_loading=True))

    def on_paginated_table_container_page_changed(
        self, event: PaginatedTableContainer.PageChanged
    ) -> None:
        """Handle page navigation"""
        self.run_worker(self.refresh_targets())

    def on_paginated_table_container_page_size_changed(
        self, event: PaginatedTableContainer.PageSizeChanged
    ) -> None:
        """Handle page size changes from auto-sizing"""
        # Refetch data with new page size
        self.run_worker(self.refresh_targets())

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "refresh-btn":
            await self.action_refresh()
        elif event.button.id == "new-target-btn":
            self.action_new_target()
        elif event.button.id == "edit-target-btn":
            self.action_edit_target()
        elif event.button.id == "delete-target-btn":
            self.action_delete_target()

    async def action_refresh(self) -> None:
        """Refresh targets"""
        await self.refresh_targets(show_loading=True)
        self.notify("Targets refreshed", timeout=2)

    def action_new_target(self) -> None:
        """Show the create target modal"""
        self._show_create_target_modal()

    def action_edit_target(self) -> None:
        """Show the edit target modal for the selected target"""
        table = self.query_one("#target-table", TargetTable)
        selected_target = table.get_selected_target()

        if selected_target is None:
            self.notify("No target selected", severity="warning", timeout=2)
            return

        self._show_edit_target_modal(selected_target)

    def action_delete_target(self) -> None:
        """Delete the selected target after confirmation"""
        table = self.query_one("#target-table", TargetTable)
        selected_target = table.get_selected_target()

        if selected_target is None:
            self.notify("No target selected", severity="warning", timeout=2)
            return

        self._confirm_delete_target(selected_target)

    @work(exclusive=True)
    async def _confirm_delete_target(self, target) -> None:
        """Worker to confirm and delete a target"""
        target_name = getattr(target, 'name', 'Unknown')
        target_id = str(getattr(target, 'id', ''))

        confirmed = await self.app.push_screen_wait(
            ConfirmModal(
                title="Delete Target",
                message=f"Are you sure you want to delete target '[bold]{target_name}[/bold]'?\n\nThis action cannot be undone.",
                confirm_label="Delete",
                danger=True
            )
        )

        if confirmed:
            try:
                await self.bbot_app.data_service.delete_target(target_id)
                self.notify(f"Target '{target_name}' deleted", timeout=3)
                await self.refresh_targets()
            except Exception as e:
                self.notify(f"Failed to delete target: {e}", severity="error", timeout=5)

    @work(exclusive=True)
    async def _show_edit_target_modal(self, target) -> None:
        """Worker to show the edit target modal and handle result"""
        import asyncio

        result = await self.app.push_screen_wait(TargetModal(target=target))

        if result is not None:
            try:
                await self.bbot_app.data_service.update_target(
                    target_id=result["id"],
                    name=result["name"],
                    description=result["description"],
                    target=result["target"],
                    seeds=result["seeds"],
                    blacklist=result["blacklist"],
                    strict_dns_scope=result["strict_dns_scope"],
                )

                self.notify("Target updated successfully!", timeout=3)

                # Wait for API to process
                await asyncio.sleep(0.5)

                # Refresh the targets list
                await self.refresh_targets()

            except Exception as e:
                self.notify(f"Failed to update target: {e}", severity="error", timeout=5)

    @work(exclusive=True)
    async def _show_create_target_modal(self) -> None:
        """Worker to show the create target modal and handle result"""
        import asyncio

        result = await self.app.push_screen_wait(TargetModal())

        if result is not None:
            # User submitted the form
            try:
                # Debug: Log what we received from the modal
                self.app.log.info(f"Modal result: name={result['name']!r}, description={result['description']!r}")
                self.app.log.info(f"Modal result: target={result['target']}, seeds={result['seeds']}")

                # Create the target
                await self.bbot_app.data_service.create_target(
                    name=result["name"],
                    description=result["description"],
                    target=result["target"],
                    seeds=result["seeds"],
                    blacklist=result["blacklist"],
                    strict_dns_scope=result["strict_dns_scope"],
                )

                self.notify("Target created successfully!", timeout=3)

                # Wait a moment for the API to fully save/index the target
                await asyncio.sleep(1.0)

                # Refresh the targets list
                await self.refresh_targets()

            except Exception as e:
                self.notify(f"Failed to create target: {e}", severity="error", timeout=5)

    def action_focus_filter(self) -> None:
        """Focus the filter input"""
        filter_bar = self.query_one("#target-filter", FilterBar)
        filter_bar.focus()

    def action_clear_filter(self) -> None:
        """Clear the filter"""
        filter_bar = self.query_one("#target-filter", FilterBar)
        filter_bar.clear_filter()
        self.filter_text = ""
        # Reset pagination when filter is cleared
        pagination = self.query_one("#target-pagination", PaginatedTableContainer)
        pagination.reset_to_first_page()
