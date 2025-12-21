"""
CLI integration for BBOT Server TUI
"""
from bbot_server.cli.base import BaseBBCTL, subcommand


class TUICTL(BaseBBCTL):
    """
    Terminal UI command for BBOT Server

    Launches a full-screen interactive terminal interface for monitoring
    and managing BBOT scans, assets, findings, and agents.
    """

    command = "tui"
    help = "Interactive terminal interface"
    short_help = "Interactive terminal interface"
    attach_to = "bbctl"
    _invoke_without_command = True

    @subcommand(help="Launch the BBOT Server Terminal UI")
    def launch(self):
        """Launch the TUI application"""
        from bbot_server.cli.tui.app import BBOTServerTUI

        app = BBOTServerTUI(
            bbot_server=self.bbot_server,
            config=self.config
        )

        try:
            app.run()
        except Exception as e:
            self.log.error(f"TUI error: {e}")
            raise
