from pathlib import Path

applet_dir = Path(__file__).parent

available_applets = []
for p in applet_dir.iterdir():
    if p.is_file() and p.suffix.lower() == ".py" and not p.stem.startswith("_"):
        available_applets.append(p.stem)
