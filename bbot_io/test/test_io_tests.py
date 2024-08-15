from pathlib import Path


def test_io_tests():
    """
    a test to test the tests
    """
    # require test for every backend
    from bbot_io.backends import backend_choices

    backends_test_dir = Path(__file__).parent / "backends"
    backend_tests = [f.stem for f in backends_test_dir.iterdir() if f.is_file() and f.suffix == ".py"]

    for backend in backend_choices:
        assert f"test_{backend}" in backend_tests, f"No test for {backend} backend"

    # require test for every applet
    from bbot_io.applets import available_applets

    applets_test_dir = Path(__file__).parent / "applets"
    applet_tests = [f.stem for f in applets_test_dir.iterdir() if f.is_file() and f.suffix == ".py"]

    for applet in available_applets:
        assert applet in applet_tests, f"No test for {applet} applet"
