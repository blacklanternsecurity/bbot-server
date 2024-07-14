from pathlib import Path


def test_io_tests():
    """
    a test to test the tests
    """
    from bbot_io.backends import backend_choices

    test_dir = Path(__file__).parent
    test_files = [f.stem for f in test_dir.iterdir() if f.is_file() and f.suffix == ".py"]

    for backend in backend_choices:
        assert f"test_{backend}" in test_files, f"No test for {backend} backend"
