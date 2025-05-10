import orjson
import subprocess

from bbot_server.models.preset_models import Preset
from tests.conftest import BBCTL_COMMAND, BBOT_SERVER_TEST_DIR


def test_cli_presetctl(bbot_server_http):
    # we shouldn't have any presets yet
    command = BBCTL_COMMAND + ["scan", "preset", "list", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    assert process.stdout == ""

    # create a preset
    preset_yaml = """
    name: test preset
    description: test preset description
    targets:
      - evilcorp.com
    """
    preset_file = BBOT_SERVER_TEST_DIR / "preset.yaml"
    preset_file.unlink(missing_ok=True)
    preset_file.write_text(preset_yaml)
    process = subprocess.run(
        BBCTL_COMMAND + ["--no-color", "scan", "preset", "create", str(preset_file)], capture_output=True, text=True
    )
    assert process.returncode == 0
    assert "Preset created successfully" in process.stderr

    # list presets
    command = BBCTL_COMMAND + ["scan", "preset", "list", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    presets = [Preset(preset=orjson.loads(line)) for line in process.stdout.splitlines()]
    assert len(presets) == 1
    assert presets[0].name == "test preset"
    assert presets[0].description == "test preset description"
    # target should have been removed
    assert not "targets" in presets[0].preset

    # update the preset
    preset_yaml = """
    name: test preset updated
    description: test preset description updated
    targets:
      - evilcorp.com
      - evilcorp.net
    """
    preset_file.write_text(preset_yaml)
    process = subprocess.run(
        BBCTL_COMMAND + ["--no-color", "scan", "preset", "update", "--name", "test preset", str(preset_file)],
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0
    assert "Preset updated successfully" in process.stderr

    # get preset by name
    command = BBCTL_COMMAND + ["scan", "preset", "get", "test preset updated", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    preset = Preset(preset=orjson.loads(process.stdout))
    assert preset.name == "test preset updated"
    assert preset.description == "test preset description updated"
    # target should have been removed
    assert not "targets" in preset.preset

    # get preset by name (text)
    command = BBCTL_COMMAND + ["scan", "preset", "get", "test preset updated"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    assert "test preset updated" in process.stdout

    # try to make new preset with same name
    process = subprocess.run(
        BBCTL_COMMAND + ["scan", "preset", "create", str(preset_file)], capture_output=True, text=True
    )
    assert process.returncode == 1
    assert "Preset with name 'test preset updated' already exists" in process.stderr

    # make new preset
    preset_yaml = """
    name: test preset 2
    targets:
      - evilcorp.com
    """
    preset_file.write_text(preset_yaml)
    process = subprocess.run(
        BBCTL_COMMAND + ["scan", "preset", "create", str(preset_file)], capture_output=True, text=True
    )
    assert process.returncode == 0
    assert "Preset created successfully" in process.stderr
    preset_json = orjson.loads(process.stdout)
    assert preset_json["name"] == "test preset 2"

    # list presets
    command = BBCTL_COMMAND + ["scan", "preset", "list", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    presets = [Preset(preset=orjson.loads(line)) for line in process.stdout.splitlines()]
    assert len(presets) == 2
    assert {p.name for p in presets} == {"test preset updated", "test preset 2"}

    # delete preset
    process = subprocess.run(
        BBCTL_COMMAND + ["scan", "preset", "delete", "test preset updated"], capture_output=True, text=True
    )
    assert process.returncode == 0
    assert "Preset deleted successfully" in process.stderr

    # list presets
    command = BBCTL_COMMAND + ["scan", "preset", "list", "--json"]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0
    presets = [Preset(preset=orjson.loads(line)) for line in process.stdout.splitlines()]
    assert len(presets) == 1
    assert presets[0].name == "test preset 2"
