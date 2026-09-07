from uuid import UUID
from typing import Any
from pymongo.errors import DuplicateKeyError

from bbot_server.modules.presets.presets_models import Preset
from bbot_server.applets.base import BaseApplet, api_endpoint


class PresetsApplet(BaseApplet):
    name = "Presets"
    description = "manage BBOT scan presets"
    model = Preset
    attach_to = "scans"

    @api_endpoint("/get/{preset_id}", methods=["GET"], summary="Get a preset by its name or id", mcp=True)
    async def get_preset(self, preset_id: UUID | str) -> Preset:
        try:
            query = {"id": str(UUID(str(preset_id)))}
        except Exception:
            query = {"name": str(preset_id)}
        preset = await self.collection.find_one(query)
        if preset is None:
            raise self.BBOTServerNotFoundError(f"Preset not found: {query}")
        return Preset(**preset)

    @api_endpoint("/list", methods=["GET"], summary="List all presets", mcp=True)
    async def get_presets(self) -> list[Preset]:
        presets = await self.collection.find().to_list(length=None)
        return [Preset(**preset) for preset in presets]

    @api_endpoint("/create", methods=["POST"], summary="Create a new preset", mcp=True)
    async def create_preset(self, preset: dict[str, Any]) -> Preset:
        preset = Preset(preset=preset)
        if not preset.name:
            preset.name = await self.get_available_preset_name()
        try:
            await self.collection.insert_one(preset.model_dump())
        except DuplicateKeyError:
            raise self.BBOTServerValueError(f"Preset with name '{preset.name}' already exists")
        return preset

    @api_endpoint("/update/{preset_id}", methods=["PATCH"], summary="Update a preset by its name or id", mcp=True)
    async def update_preset(self, preset_id: UUID | str, preset: dict[str, Any]) -> Preset:
        existing_preset = await self.get_preset(preset_id)
        # Create new preset with the updated dictionary
        new_preset = Preset(preset=preset)
        new_preset.id = existing_preset.id
        if not new_preset.name:
            new_preset.name = existing_preset.name
        new_preset.modified = self.helpers.utc_now()
        try:
            await self.collection.replace_one({"id": str(existing_preset.id)}, new_preset.model_dump())
        except DuplicateKeyError:
            raise self.BBOTServerValueError(f"Preset with name '{new_preset.name}' already exists")
        return new_preset

    @api_endpoint("/delete/{preset_id}", methods=["DELETE"], summary="Delete a preset by its name or id", mcp=True)
    async def delete_preset(self, preset_id: UUID | str) -> None:
        existing_preset = await self.get_preset(preset_id)
        await self.collection.delete_one({"id": str(existing_preset.id)})

    async def get_available_preset_name(self) -> str:
        """
        Returns a preset name that's guaranteed to not be in use, such as "Preset 1", "Preset 2", etc.
        """
        # Get all existing preset names
        existing_names = await self.collection.distinct("name")
        # Start with "Preset 1" and increment until we find an unused name
        counter = 1
        while f"Preset {counter}" in existing_names:
            counter += 1
        return f"Preset {counter}"
