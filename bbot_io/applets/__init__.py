from pathlib import Path

from bbot_io.applets._base import BaseApplet

applet_dir = Path(__file__).parent

available_applets = []
for p in applet_dir.iterdir():
    if p.is_file() and p.suffix.lower() == ".py" and not p.stem.startswith("_"):
        available_applets.append(p.stem)


class BBOTApplet(BaseApplet):

    include_apps = ["Events", "Scans", "Utils", "Targets"]

    nested = False

    def __init__(self, backend="sqlite", **kwargs):
        from bbot_io.backends import BBOTBackend

        # instantiate our IO module in the root app
        self.backend = BBOTBackend(backend, **kwargs)
        super().__init__(self.backend)
