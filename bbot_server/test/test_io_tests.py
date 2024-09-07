from pathlib import Path
from inspect import iscoroutinefunction


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
    from bbot_io.test.applets import applet_tests

    for applet in available_applets:
        assert applet in applet_tests, f"No test for {applet} applet"
        test_fn = applet_tests[applet]
        assert iscoroutinefunction(test_fn), f"{test_fn} is not an async callable function"
