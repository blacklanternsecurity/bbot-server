from pathlib import Path

from bbot_server.applets._root import RootApplet

applet_dir = Path(__file__).parent

APPLETS = []
for p in applet_dir.iterdir():
    if p.is_file() and p.suffix.lower() == ".py" and not p.stem.startswith("_"):
        APPLETS.append(p.stem)


def BBOTServerRootApplet(*args, **kwargs):
    return RootApplet(*args, **kwargs)


APP_ROOT = BBOTServerRootApplet()
