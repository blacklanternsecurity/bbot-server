from pathlib import Path

# make a list of all the applets and their file locations

applet_dir = Path(__file__).parent / "applets"

APPLETS = {}
for p in applet_dir.iterdir():
    if p.is_file() and p.suffix.lower() == ".py" and not p.stem.startswith("_"):
        APPLETS[p.stem] = p
