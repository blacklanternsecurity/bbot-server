import importlib
from pathlib import Path

applet_test_dir = Path(__file__).parent
applet_tests = {}

for p in applet_test_dir.iterdir():
    if p.is_file() and p.suffix.lower() == ".py" and not p.stem.startswith("_"):
        applet_name = p.stem
        try:
            module = importlib.import_module(f"bbot_server.test.applets.{applet_name}")
            applet_test_fn = getattr(module, f"{applet_name}_test")
            applet_tests[p.stem] = applet_test_fn
        except Exception as e:
            raise ImportError(f"Failed to load test for {p}: {e}")
