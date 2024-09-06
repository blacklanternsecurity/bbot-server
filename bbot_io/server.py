def run_server(backend, **kwargs):
    import os
    import json

    uvicorn_options = kwargs.pop("uvicorn_options", {})

    os.environ["BBOT_IO_BACKEND"] = backend
    os.environ["BBOT_IO_CONFIG"] = json.dumps(kwargs)

    import uvicorn

    uvicorn.run("bbot_io.fastapi:app", **uvicorn_options)


def main():
    import argparse
    from omegaconf import OmegaConf
    from bbot_io.backends import backend_choices

    parser = argparse.ArgumentParser(description="BBOT Server")
    parser.add_argument(
        "-b", "--backend", default="sqlite", choices=backend_choices, help=f"Which backend to use (default: sqlite)"
    )
    parser.add_argument("-p", "--port", default=8000, type=int, help="Port to listen on")
    parser.add_argument("-l", "--listen", default="127.0.0.1", help="IP address to listen on")
    parser.add_argument("-r", "--auto-reload", action="store_true", help="Auto-reload web server (for devving)")
    parser.add_argument(
        "-c",
        "--config",
        nargs="*",
        help="Custom config options in key=value format: e.g. 'url=http://bbot.io/'",
        metavar="CONFIG",
        default=[],
    )

    options = parser.parse_args()
    additional_options = OmegaConf.to_container(OmegaConf.from_cli(options.config))

    run_server(
        options.backend,
        uvicorn_options=dict(host=options.listen, port=options.port, reload=options.auto_reload),
        **additional_options,
    )


if __name__ == "__main__":
    main()
