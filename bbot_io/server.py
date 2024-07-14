def main():
    import os
    import argparse
    from bbot_io.backends import backend_choices

    parser = argparse.ArgumentParser(description="BBOT Server")
    parser.add_argument(
        "-b", "--backend", default="sqlite", choices=backend_choices, help=f"Which backend to use (default: sqlite)"
    )
    parser.add_argument("-p", "--port", default=8000, type=int, help="Port to listen on")
    parser.add_argument("-l", "--listen", default="127.0.0.1", help="IP address to listen on")
    parser.add_argument("-r", "--auto-reload", action="store_true", help="Auto-reload web server (for devving)")

    options = parser.parse_args()
    os.environ["BBOT_IO_BACKEND"] = options.backend

    import uvicorn

    uvicorn.run("bbot_io.fastapi:app", host=options.listen, port=options.port, reload=options.auto_reload)


if __name__ == "__main__":
    main()
