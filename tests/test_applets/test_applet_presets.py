import pytest

from bbot_server.models.preset_models import Preset
from bbot_server.errors import BBOTServerValueError, BBOTServerNotFoundError


# test CRUD operations on targets
async def test_applet_presets(bbot_server):
    bbot_server = await bbot_server()

    # list presets
    presets = await bbot_server.get_presets()
    assert presets == []

    # create a preset
    original_preset = Preset(
        preset={
            "name": "test preset",
            "targets": ["evilcorp.com"],
            "config": {
                "modules": ["robots"],
            },
        },
    )
    original_preset = await bbot_server.create_preset(original_preset)
    assert original_preset.id is not None

    # get preset by id
    preset = await bbot_server.get_preset(str(original_preset.id))
    assert preset.id is not None
    assert preset.name == "test preset"
    assert preset.preset["targets"] == ["evilcorp.com"]
    assert preset.preset["config"]["modules"] == ["robots"]

    # get preset by name
    preset = await bbot_server.get_preset(original_preset.name)
    assert preset.id is not None
    assert preset.name == "test preset"
    assert preset.preset["targets"] == ["evilcorp.com"]
    assert preset.preset["config"]["modules"] == ["robots"]

    # list presets
    presets = await bbot_server.get_presets()
    assert len(presets) == 1
    assert presets[0].id == preset.id
    assert presets[0].name == "test preset"
    assert presets[0].preset["targets"] == ["evilcorp.com"]
    assert presets[0].preset["config"]["modules"] == ["robots"]

    # try creating a new preset with the same name
    with pytest.raises(BBOTServerValueError):
        dup_preset = Preset(
            preset={
                "name": "test preset",
                "targets": ["evilcorp.com"],
            },
        )
        await bbot_server.create_preset(dup_preset)

    # update the preset
    updated_preset = Preset(
        preset={
            "name": "test preset updated",
            "targets": ["evilcorp.com"],
        },
    )
    updated_preset = await bbot_server.update_preset(str(original_preset.id), updated_preset)
    assert updated_preset.id == original_preset.id
    assert updated_preset.name == "test preset updated"
    assert updated_preset.preset == {"name": "test preset updated", "targets": ["evilcorp.com"]}

    # create a new preset
    new_preset = Preset(
        preset={
            "targets": ["evilcorp.com"],
        },
    )
    new_preset = await bbot_server.create_preset(new_preset)
    assert new_preset.id is not None
    assert new_preset.name == "Preset 1"
    assert new_preset.preset == {"name": "Preset 1", "targets": ["evilcorp.com"]}

    new_preset2 = Preset(
        preset={
            "targets": ["evilcorp.com"],
        },
    )
    new_preset2 = await bbot_server.create_preset(new_preset2)
    assert new_preset2.id is not None
    assert new_preset2.name == "Preset 2"

    # list presets
    presets = await bbot_server.get_presets()
    assert len(presets) == 3
    assert {p.name for p in presets} == {"Preset 1", "Preset 2", "test preset updated"}

    # delete a preset
    await bbot_server.delete_preset("test preset updated")
    presets = await bbot_server.get_presets()
    assert len(presets) == 2
    assert {p.name for p in presets} == {"Preset 1", "Preset 2"}

    with pytest.raises(BBOTServerNotFoundError):
        await bbot_server.delete_preset(original_preset.name)

    with pytest.raises(BBOTServerNotFoundError):
        await bbot_server.get_preset(original_preset.name)

    with pytest.raises(BBOTServerValueError):
        new_preset2.name = "Preset 1"
        await bbot_server.update_preset(str(new_preset2.id), new_preset2)
