from pathlib import Path


cli_dir = Path(__file__).parent.parent / "bbot_server" / "cli"
cli_tests_dir = Path(__file__).parent / "test_cli"

cli_files = [p.stem for p in cli_dir.rglob("*.py") if p.stem.endswith("ctl")]
cli_test_files = [p.stem for p in cli_tests_dir.rglob("*.py") if p.stem.startswith("test_")]

def test_cli_tests():
    # make sure each CLI has a test
    for cli_file in cli_files:
        assert f"test_cli_{cli_file}" in cli_test_files, f"No test file found for CLI '{cli_file}'"
