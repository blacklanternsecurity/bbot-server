from uuid import UUID

from bbot_server.cli import common
from bbot_server.cli.base import BaseBBCTL, subcommand


class APIKeyCTL(BaseBBCTL):
    command = "apikey"
    help = "Manage BBOT server API keys"
    short_help = "Manage BBOT server API keys"
    attach_to = "server"

    @subcommand(help="List all BBOT server API keys")
    def list(
        self,
        json: common.json = False,
    ):
        valid_secrets = sorted(self.bbcfg.get_api_keys())
        if json:
            self.print_raw_line(self.orjson.dumps(valid_secrets))
            return
        table = self.Table()
        table.add_column("API Key", style=self.COLOR)
        for api_key in valid_secrets:
            table.add_row(api_key)
        self.stdout.print(table)

    @subcommand(help="Create a new API key")
    def add(self):
        api_key = self.bbcfg.add_api_key()
        self.log.info(f"New API key added. Please restart the server for the new key to be recognized:")
        self.log.info(f"    - API KEY: {api_key}")

    @subcommand(help="Revoke an API key")
    def delete(self, api_key: UUID):
        try:
            self.bbcfg.revoke_api_key(api_key)
        except KeyError:
            raise self.BBOTServerError(f"API key {api_key} not found in config file")
