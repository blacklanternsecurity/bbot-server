"""
Target detail widget for BBOT Server TUI
"""

from textual.app import ComposeResult
from textual.widgets import Static
from textual.containers import VerticalScroll

from bbot_server.cli.tui.utils.formatters import format_timestamp


class TargetDetail(VerticalScroll):
    """Widget for displaying detailed target information"""

    def compose(self) -> ComposeResult:
        """Create the static text widget"""
        yield Static("[dim]No target selected[/dim]", id="target-detail-text")

    def update_target(self, target) -> None:
        """
        Update the detail view with target information

        Args:
            target: Target model
        """
        try:
            detail_text = self.query_one("#target-detail-text", Static)
        except Exception:
            return

        if not target:
            detail_text.update("[dim]No target selected[/dim]")
            return

        # Build detail text
        details = []

        # Basic info
        details.append(f"[bold]Name:[/bold] {getattr(target, 'name', 'UNKNOWN')}")
        details.append(f"[bold]Description:[/bold] {getattr(target, 'description', 'N/A')}")

        # Default status
        is_default = getattr(target, "default", False)
        details.append(f"[bold]Default Target:[/bold] {'Yes' if is_default else 'No'}")

        # ID
        target_id = getattr(target, "id", "N/A")
        details.append(f"[bold]ID:[/bold] {target_id}")

        # Target list
        target_list = getattr(target, "target", [])
        if target_list:
            targets_str = ", ".join(target_list)
            details.append(f"[bold]Targets ({len(target_list)}):[/bold] {targets_str}")
        else:
            details.append(f"[bold]Targets:[/bold] (none)")

        # Seeds
        seeds = getattr(target, "seeds", [])
        if seeds:
            seeds_str = ", ".join(seeds)
            details.append(f"[bold]Seeds ({len(seeds)}):[/bold] {seeds_str}")

        # Blacklist
        blacklist = getattr(target, "blacklist", [])
        if blacklist:
            blacklist_str = ", ".join(blacklist)
            details.append(f"[bold]Blacklist ({len(blacklist)}):[/bold] {blacklist_str}")

        # Strict DNS scope
        strict_dns = getattr(target, "strict_scope", False)
        details.append(f"[bold]Strict DNS Scope:[/bold] {'Yes' if strict_dns else 'No'}")

        # Sizes
        target_size = getattr(target, "target_size", 0)
        seed_size = getattr(target, "seed_size", 0)
        blacklist_size = getattr(target, "blacklist_size", 0)
        details.append(f"[bold]Target Size:[/bold] {target_size}")
        details.append(f"[bold]Seed Size:[/bold] {seed_size}")
        details.append(f"[bold]Blacklist Size:[/bold] {blacklist_size}")

        # Hashes
        hash_val = getattr(target, "hash", "N/A")
        details.append(f"[bold]Hash:[/bold] {hash_val}")

        scope_hash = getattr(target, "scope_hash", "N/A")
        details.append(f"[bold]Scope Hash:[/bold] {scope_hash}")

        # Timestamps
        created = getattr(target, "created", 0)
        details.append(f"[bold]Created:[/bold] {format_timestamp(created)}")

        modified = getattr(target, "modified", 0)
        details.append(f"[bold]Modified:[/bold] {format_timestamp(modified)}")

        detail_text.update("\n\n".join(details))
