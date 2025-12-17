from textual import on
from textual.events import Click
from textual.reactive import var
from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll, Vertical, Horizontal
from textual.widgets import Footer, Header, ListView, ListItem, Label, TextArea, Button, Switch, Input

from bbot.scanner import Scanner, Preset
from bbot.core.helpers.names_generator import random_name

from .themes import TEXTUAL_THEME


class ScanEditor(App):
    CSS = """
#nav-bar {
    width: 25 ;
    dock: left;

    &.-highlight {
        background: #1a1a1a;
    }

    ListView {
        background-tint: #1a1a1a;
    }

    ListItem {
        padding: 1 3;
        &.-highlight {
            color: #ff8400;
            background: black;
            text-style: bold;
            outline-left: thick #ff8400;
        }
    }
}

Button {
    margin: 0 1;
    text-style: none;
}

#buttons {
    dock: bottom;
    height: 3;
    width: 100%;
    align-horizontal: right;
}

.nav-tab {
    width: 100%;
    padding: 0;
    margin: 0;
}

.label {
    padding: 1;
}

#buttons-right {
    width: auto;
}

#scan-name-container {
    height: 3;
    text-style: bold;
}

#scan-name {
    outline: outer #ff8400;
}

#scan-name-label {
    background: #ff8400;
    color: black;
}

#editor-label {
    padding: 1 3;
    color: #808080;
}
"""

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    show_tree = var(True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scan_name = random_name()
        self._start_scan = False
        self._current_pane = "target"
        self._text_panes = {
            "target": "",
            "whitelist": "",
            "blacklist": "",
            "preset": f"description: {self.scan_name}\n",
        }
        self._descriptions = {
            "target": "Paste your IPs, domains etc. in here. These are used to seed the scan.",
            "whitelist": "If left blank, will default to the target.",
            "blacklist": "Takes ultimate precedence over whitelist and target.",
            "preset": "BBOT Preset in YAML format. Put your API keys, etc. in here.",
        }
        self._success = False

    def notify(self, *args, **kwargs):
        if "timeout" not in kwargs:
            kwargs["timeout"] = 1
        super().notify(*args, **kwargs)

    def do_target(self):
        self.notify("Target")

    def compose(self) -> ComposeResult:
        """Compose our UI."""
        yield Header()
        with Horizontal(id="scan-name-container"):
            yield Label("Scan Name", id="scan-name-label", classes="label")
            yield Input(value=self.scan_name, placeholder="Scan Name", id="scan-name")
        with Container(id="scan-editor"):
            with Vertical(id="nav-bar"):
                yield ListView(
                    ListItem(Label("Target", classes="nav-tab target-button"), classes="target-button"),
                    ListItem(Label("Whitelist", classes="nav-tab whitelist-button"), classes="whitelist-button"),
                    ListItem(Label("Blacklist", classes="nav-tab blacklist-button"), classes="blacklist-button"),
                    ListItem(Label("Preset", classes="nav-tab preset-button"), classes="preset-button"),
                )
            with VerticalScroll(id="code-view"):
                with Vertical(id="editor-container"):
                    yield Label("", id="editor-label")
                    yield TextArea.code_editor("", id="code-editor")
                    with Horizontal(id="buttons"):
                        with Horizontal(id="buttons-right"):
                            yield Label("Start Scan", classes="label")
                            yield Switch(value=False, id="start-scan", animate=False)
                            yield Button("SAVE", variant="success", id="save")
                            yield Button("QUIT", id="quit")
        yield Footer()

    def save_text(self):
        self.scan_name = self.query_one("#scan-name", Input).value
        self._text_panes[self._current_pane] = self.query_one("#code-editor", TextArea).text

    def switch_text_pane(self, var_name, syntax=None):
        if var_name not in self._text_panes:
            raise ValueError(f"Invalid variable name: {var_name}")
        self.save_text()
        self._current_pane = var_name
        text_area = self.query_one("#code-editor", TextArea)
        text_area.text = self._text_panes[var_name]
        text_area.language = syntax
        label = self.query_one("#editor-label")
        label.update(self._descriptions[var_name])
        self.focus_editor()

    @on(Click)
    def on_click(self, event: Click):
        if "target-button" in event.widget.classes:
            self.switch_text_pane("target")
        elif "whitelist-button" in event.widget.classes:
            self.switch_text_pane("whitelist")
        elif "blacklist-button" in event.widget.classes:
            self.switch_text_pane("blacklist")
        elif "preset-button" in event.widget.classes:
            self.switch_text_pane("preset", syntax="yaml")

    def select_all_text(self):
        self.query_one("#code-editor", TextArea).select_all()

    def on_key(self, event):
        if event.key == "ctrl+a":
            event.prevent_default()
            self.select_all_text()
        elif event.key == "ctrl+c":
            event.prevent_default()
            self.notify("Press CTRL+Q to quit", severity="error")

    def on_switch_changed(self, event: Switch.Changed):
        if event.switch.id == "start-scan":
            self._start_scan = event.value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button

        if button.id == "quit":
            self.exit()
        elif button.id == "save":
            self.save_text()
            self._success = True
            self.exit()

    def focus_editor(self):
        self.query_one("#code-editor", TextArea).focus()

    def on_mount(self) -> None:
        # Set BBOT theme
        self.register_theme(TEXTUAL_THEME)
        self.theme = "bbot"

        self.switch_text_pane("target")

    def make_scan(self):
        self.run()
        if not self._success:
            return None, False

        targets = [t for t in self._text_panes["target"].splitlines() if t]
        whitelist = [w for w in self._text_panes["whitelist"].splitlines() if w]
        blacklist = [b for b in self._text_panes["blacklist"].splitlines() if b]

        preset_str = self._text_panes["preset"].strip()
        base_preset = Preset.from_yaml_string(preset_str)

        # validate targets + preset by instantiating a real scan
        scan = Scanner(
            *targets, scan_name=self.scan_name, whitelist=whitelist, blacklist=blacklist, preset=base_preset
        )
        preset_dict_sanitized = scan.preset.to_dict()

        print(scan.preset.to_dict(include_target=True))

        from bbot_server.applets.scans import Scan

        scan = Scan(
            name=self.scan_name,
            preset=preset_dict_sanitized,
            target=targets,
            whitelist=whitelist,
            blacklist=blacklist,
        )

        return scan, self._start_scan
