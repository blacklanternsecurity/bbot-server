import yaml
from pathlib import Path
from typer import Argument

from bbot_server.cli import common
from bbot_server.cli.base import BaseBBCTL, subcommand, Option, Annotated


class PresetCTL(BaseBBCTL):
    command = "preset"
    help = "Create, update, and delete BBOT presets"
    short_help = "Manage BBOT presets"

    @subcommand(help="Create a new preset from a YAML file")
    def create(
        self,
        preset: Annotated[Path, Argument(help="Path to preset YAML file")],
        name: Annotated[str, Option("--name", "-n", help="Preset name")] = "",
        description: Annotated[str, Option("--description", "-d", help="Preset description")] = "",
    ):
        preset_dict = self._load_preset(preset)
        if name:
            preset_dict["name"] = name
        if description:
            preset_dict["description"] = description
        if not preset_dict.get("name", ""):
            preset_dict["name"] = preset.stem
        new_preset = self.bbot_server.create_preset(preset_dict)
        self.log.info(f"Preset created successfully")
        self.print_pydantic_json(new_preset, colorize=True)

    @subcommand(help="Update a preset by name or ID")
    def update(
        self,
        id: Annotated[str, Option("--name", "-n", "--id", "-i", help="Preset name or ID")],
        preset: Annotated[Path, Argument(help="Path to preset YAML file")],
    ):
        preset_dict = self._load_preset(preset)
        self.bbot_server.update_preset(id, preset_dict)
        self.log.info(f"Preset updated successfully")

    @subcommand(help="Get a preset by name or ID")
    def get(
        self,
        id: Annotated[str, Argument(help="Preset name or ID")],
        json: common.json = False,
    ):
        preset = self.bbot_server.get_preset(id)
        if json:
            self.print_raw_line(self.orjson.dumps(preset.preset))
        else:
            self.print_pydantic_json(preset)

    @subcommand(help="Delete a preset by name or ID")
    def delete(
        self,
        id: Annotated[str, Argument(help="Preset name or ID")],
    ):
        self.bbot_server.delete_preset(id)
        self.log.info(f"Preset deleted successfully")

    @subcommand(help="List presets")
    def list(
        self,
        json: common.json = False,
    ):
        preset_list = self.bbot_server.get_presets()

        if json:
            for preset in preset_list:
                self.print_raw_line(self.orjson.dumps(preset.preset))
            return

        table = self.Table()
        table.add_column("Name", style=self.COLOR)
        table.add_column("Description")
        table.add_column("Created", style=self.DARK_COLOR)
        table.add_column("Modified", style=self.DARK_COLOR)
        table.add_column("Preset")
        for preset in preset_list:
            table.add_row(
                preset.name,
                preset.description,
                self.timestamp_to_human(preset.created),
                self.timestamp_to_human(preset.modified),
                self.highlight_json(preset.preset),
            )
        self.stdout.print(table)

    def _load_preset(self, preset: Path) -> dict:
        if not preset.resolve().is_file():
            raise self.BBOTServerValueError(f"Unable to find preset at {preset}")
        preset_dict = yaml.safe_load(preset.read_text())
        if not isinstance(preset_dict, dict):
            raise self.BBOTServerValueError("Preset must be a dictionary")
        return preset_dict
