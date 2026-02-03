"""
Target modal for BBOT Server TUI - handles both create and edit
"""
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Container, Horizontal
from textual.widgets import Static, Input, TextArea, Button, Checkbox


class TargetModal(ModalScreen[dict | None]):
    """Modal dialog for creating or editing a target"""

    CSS = """
    TargetModal {
        align: center middle;
    }

    #dialog {
        width: 80;
        height: auto;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }

    #title {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        color: #FF8400;
        padding: 0 0 1 0;
    }

    .form-label {
        width: 100%;
        padding: 1 0 0 0;
        color: #FF8400;
    }

    Input {
        width: 100%;
        margin: 0 0 0 0;
        border: tall #808080;
    }

    Input:focus {
        border: tall #FF8400;
    }

    TextArea {
        width: 100%;
        height: 5;
        margin: 0 0 0 0;
        border: tall #808080;
    }

    TextArea:focus {
        border: tall #FF8400;
    }

    #button-container {
        width: 100%;
        height: auto;
        align: center middle;
        padding: 1 0 0 0;
    }

    Button {
        margin: 0 1;
    }
    """

    def __init__(self, target=None) -> None:
        """Initialize the modal

        Args:
            target: Optional target model for edit mode. If None, create mode.
        """
        super().__init__()
        self.target = target
        self.is_edit_mode = target is not None

    def compose(self) -> ComposeResult:
        """Create the modal dialog"""
        # Get initial values from target if editing
        name = getattr(self.target, 'name', '') or '' if self.target else ''
        description = getattr(self.target, 'description', '') or '' if self.target else ''
        target_list = getattr(self.target, 'target', []) or [] if self.target else []
        seeds_list = getattr(self.target, 'seeds', None) or [] if self.target else []
        blacklist_list = getattr(self.target, 'blacklist', []) or [] if self.target else []
        strict_scope = getattr(self.target, 'strict_dns_scope', False) if self.target else False

        title = "Edit Target" if self.is_edit_mode else "Create New Target"
        submit_label = "Save" if self.is_edit_mode else "Create"
        name_placeholder = "Target name" if self.is_edit_mode else "Target name (leave empty for auto-generated)"

        with Container(id="dialog"):
            yield Static(title, id="title")

            yield Static("Name:", classes="form-label")
            yield Input(value=name, placeholder=name_placeholder, id="name-input")

            yield Static("Description:", classes="form-label")
            yield Input(value=description, placeholder="Target description", id="description-input")

            yield Static("Target (one per line - domains, IPs, CIDRs, URLs):", classes="form-label")
            yield TextArea(text='\n'.join(target_list), id="target-input")

            yield Static("Seeds (one per line - leave empty to use target list):", classes="form-label")
            yield TextArea(text='\n'.join(seeds_list) if seeds_list else '', id="seeds-input")

            yield Static("Blacklist (one per line):", classes="form-label")
            yield TextArea(text='\n'.join(blacklist_list), id="blacklist-input")

            yield Checkbox("Strict DNS Scope", value=strict_scope, id="strict-scope-checkbox")

            with Horizontal(id="button-container"):
                yield Button(submit_label, id="submit-btn", variant="primary")
                yield Button("Cancel", id="cancel-btn", variant="default")

    def on_mount(self) -> None:
        """Focus the name input when modal opens"""
        self.query_one("#name-input", Input).focus()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "cancel-btn":
            self.dismiss(None)
        elif event.button.id == "submit-btn":
            await self.handle_submit()

    async def handle_submit(self) -> None:
        """Collect form data and dismiss with result"""
        # Get input values
        name = self.query_one("#name-input", Input).value.strip()
        description = self.query_one("#description-input", Input).value.strip()
        target_text = self.query_one("#target-input", TextArea).text.strip()
        seeds_text = self.query_one("#seeds-input", TextArea).text.strip()
        blacklist_text = self.query_one("#blacklist-input", TextArea).text.strip()
        strict_scope = self.query_one("#strict-scope-checkbox", Checkbox).value

        # Parse lists (split by newlines and filter empty)
        target_list = [line.strip() for line in target_text.split('\n') if line.strip()]
        seeds_list = [line.strip() for line in seeds_text.split('\n') if line.strip()] if seeds_text else None
        blacklist_list = [line.strip() for line in blacklist_text.split('\n') if line.strip()]

        # Validation
        if self.is_edit_mode:
            # Edit mode: name is required
            if not name:
                self.app.notify("Target name is required", severity="error", timeout=3)
                return
        else:
            # Create mode: must have at least target or seeds
            if not target_list and not seeds_list:
                self.app.notify("Must provide at least one target or seed", severity="error", timeout=3)
                return

        # Build result
        result = {
            "name": name if name else "",
            "description": description,
            "target": target_list if target_list else [],
            "seeds": seeds_list,
            "blacklist": blacklist_list,
            "strict_dns_scope": strict_scope,
        }

        # Include ID for edit mode
        if self.is_edit_mode:
            result["id"] = str(getattr(self.target, 'id', ''))

        self.dismiss(result)


# Alias for backwards compatibility
CreateTargetModal = TargetModal
