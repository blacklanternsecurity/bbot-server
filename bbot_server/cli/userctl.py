from pydantic import UUID4
from omegaconf import OmegaConf

from bbot_server.cli.base import BaseBBCTL, subcommand


class UserCTL(BaseBBCTL):
    command = "user"
    help = "Manage BBOT server users"
    short_help = "Manage BBOT server users"

    def setup(self):
        self.existing_config = OmegaConf.load(self.root.config_path)

    @subcommand(help="List all BBOT server users")
    def list(self):
        valid_secrets = self.existing_config.get("valid_secrets", {})
        table = self.Table()
        table.add_column("Secret ID", style=self.COLOR)
        table.add_column("Secret Key")
        for secret_id in valid_secrets:
            table.add_row(secret_id, "********")
        self.stdout.print(table)

    @subcommand(help="Add a new user to BBOT server")
    def add(self):
        api_key = self.bbcfg.add_api_key()
        self.log.info(f"New API key added. Please restart the server for the new key to be recognized:")
        self.log.info(f"    - API KEY: {api_key}")

    @subcommand(help="Revoke an API key")
    def delete(self, api_key: UUID4):
        try:
            self.bbcfg.revoke_api_key(api_key)
        except KeyError:
            raise self.BBOTServerError(f"API key {api_key} not found in config file")
