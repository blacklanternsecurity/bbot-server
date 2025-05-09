import uuid
from pydantic import UUID4
from pymongo.errors import DuplicateKeyError

from bbot_server.models.preset_models import Preset
from bbot_server.applets._base import BaseApplet, api_endpoint


class PresetsApplet(BaseApplet):
    name = "Presets"
    description = "manage BBOT scan presets"
    model = Preset

    @api_endpoint("/get/{preset_id}", methods=["GET"], summary="Get a preset by its name or id")
    async def get_preset(self, preset_id: UUID4 | str) -> Preset:
        try:
            query = {"id": str(UUID4(preset_id))}
        except ValueError:
            query = {"name": preset_id}
        preset = await self.collection.find_one(query)
        if preset is None:
            raise self.BBOTServerNotFoundError(f"Preset not found: {query}")
        return Preset(**preset)

    @api_endpoint("/list", methods=["GET"], summary="List all presets")
    async def list_presets(self) -> list[Preset]:
        presets = await self.collection.find().to_list(length=None)
        return [Preset(**preset) for preset in presets]

    @api_endpoint("/create", methods=["POST"], summary="Create a new preset")
    async def create_preset(self, preset: Preset) -> Preset:
        preset.id = uuid.uuid4()
        if not preset.name:
            preset.name = await self.get_available_preset_name()
        try:
            await self.collection.insert_one(preset.model_dump())
        except DuplicateKeyError:
            raise self.BBOTServerValueError(f"Preset with name {preset.name} already exists")
        return preset

    @api_endpoint("/update/{preset_id}", methods=["PATCH"], summary="Update a preset by its name or id")
    async def update_preset(self, preset_id: UUID4 | str, preset: Preset) -> Preset:
        existing_preset = await self.get_preset(preset_id)
        preset.id = existing_preset.id
        try:
            await self.collection.replace_one({"id": str(existing_preset.id)}, preset.model_dump())
        except DuplicateKeyError:
            raise self.BBOTServerValueError(f"Preset with name {preset.name} already exists")
        return preset

    @api_endpoint("/delete/{preset_id}", methods=["DELETE"], summary="Delete a preset by its name or id")
    async def delete_preset(self, preset_id: UUID4 | str) -> None:
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
