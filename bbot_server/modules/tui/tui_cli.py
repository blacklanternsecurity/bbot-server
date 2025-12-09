from bbot_server.cli.base import BaseBBCTL


class TUI(BaseBBCTL):
    command = "ui"
    help = "Textual UI Proof of Concept for BBOT"
    short_help = "Textual UI Proof of Concept for BBOT"
    attach_to = "scan"

    _invoke_without_command = True
    _no_args_is_help = False

    def main(self):
        from bbot_server.modules.tui.scan_editor import ScanEditor

        app = ScanEditor()
        app.run()
