import re
from importlib.metadata import version
from pathlib import Path

import yaml
from packaging.version import Version

chart_file = Path(__file__).parent.parent / "helm" / "Chart.yaml"


def test_chart_declares_the_package_version():
    declared = Version(version("bbot-server"))
    chart = yaml.safe_load(chart_file.read_text())
    assert Version(chart["appVersion"]) == declared
    assert Version(chart["version"]) == declared
    assert re.fullmatch(r"\d+\.\d+\.\d+(-rc\.\d+)?", chart["version"])
