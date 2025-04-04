import sys

# import importlib
from pathlib import Path

from bbot_server.applets import APPLETS
# from tests.test_applets.base import BaseAppletTest


applet_tests_dir = Path(__file__).parent / "test_applets"
sys.path.insert(0, str(applet_tests_dir.parent.parent))

applet_test_files = list(applet_tests_dir.glob("test_*.py"))
applet_test_files.sort(key=lambda p: p.name)
applet_names = [p.stem.split("test_applet_")[-1] for p in applet_test_files]


def test_applet_tests():
    # make sure each applet has a .py file
    for applet_name in APPLETS:
        assert applet_name in applet_names, f'No test file found for applet "{applet_name}"'

    # make sure each test file has a test class
    # for applet_name, applet_file in zip(applet_names, applet_test_files):
    #     import_path = f"tests.test_applets.test_applet_{applet_name}"
    #     applet_test_variables = importlib.import_module(import_path, "tests")
    #     applet_pass = False
    #     for var_name, var_value in applet_test_variables.__dict__.items():
    #         if BaseAppletTest in getattr(var_value, "__bases__", []):
    #             applet_pass = True
    #             break
    #         # if callable(var_value) and var_name == f"test_applet_{applet_name}":
    #         #     applet_pass = True
    #         #     break
    #     assert applet_pass, f"Couldn't find a test class for {applet_name} in {applet_file}"
