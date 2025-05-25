import uuid
from pydantic import UUID4
from hashlib import blake2s
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
        for secret_id in valid_secrets:
            table.add_row(secret_id)
        self.stdout.print(table)

    @subcommand(help="Add a new user to BBOT server")
    def add(self):
        secret_id, secret_key, secret_key_hash = self._new_api_key()

        valid_secrets = self.existing_config.get("valid_secrets", OmegaConf.create())
        if not OmegaConf.is_dict(valid_secrets):
            raise self.BBOTServerValueError(
                f"Invalid config: valid_secrets must be a dictionary, not {type(valid_secrets)}"
            )

        valid_secrets[secret_id] = secret_key_hash

        # load the existing config and insert the new API key
        existing_config = self.existing_config.copy()
        self.log.info(f"New secret added:")
        self.log.info(f"    - ID: {secret_id}")
        self.log.info(f"    - Key: {secret_key}")
        # if no API key is set, set it to the new secret
        if existing_config.get("api_key", ""):
            self.log.warning(
                f"You already have a different API key in your config file at {self.root.config_path}. It will not be overwritten. Please make sure to save this in a secure location!"
            )
        else:
            existing_config.api_key = f"{secret_id}:{secret_key}"
            self.log.info(
                f"The new API key has been automatically saved to your config file at {self.root.config_path}."
            )
        # write out the updated config
        existing_config["valid_secrets"] = valid_secrets
        try:
            OmegaConf.save(existing_config, self.root.config_path)
        except Exception as e:
            raise self.BBOTServerError(f"Error saving config file at {self.root.config_path}: {e}") from e

    @subcommand(help="Revoke a secret by its ID")
    def delete(self, secret_id: UUID4):
        secret_id = str(secret_id)
        valid_secrets = self.existing_config.get("valid_secrets", {})
        if secret_id not in valid_secrets:
            raise self.BBOTServerError(f"Secret ID {secret_id} not found in config file at {self.root.config_path}")
        del valid_secrets[secret_id]
        self.existing_config["valid_secrets"] = valid_secrets
        try:
            OmegaConf.save(self.existing_config, self.root.config_path)
            self.log.info(f"Secret ID {secret_id} successfully deleted from {self.root.config_path}")
        except Exception as e:
            raise self.BBOTServerError(f"Error saving config file at {self.root.config_path}: {e}") from e

    def _new_api_key(self):
        secret_id = str(uuid.uuid4())
        secret_key = str(uuid.uuid4())
        secret_key_hash = blake2s(secret_key.encode()).hexdigest()
        return secret_id, secret_key, secret_key_hash
