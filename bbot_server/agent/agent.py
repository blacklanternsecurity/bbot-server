import orjson
import asyncio
import inspect
import logging
import traceback
import websockets
from contextlib import suppress
from typing import Callable, Any
from urllib.parse import urlparse, urlunparse, urljoin

from bbot import Scanner, Preset

from bbot_server.config import BBOT_SERVER_CONFIG
from bbot_server.errors import BBOTServerValueError
from bbot_server.models.scan_models import ScanRun
from bbot_server.utils.async_utils import async_to_sync_class
from bbot_server.models.agent_models import AgentResponse

default_server_url = BBOT_SERVER_CONFIG.get("url", "http://localhost:8807/v1/")
default_bbot_preset = BBOT_SERVER_CONFIG.get("agent", {}).get("base_preset", {})


VALID_AGENT_COMMANDS = {}


# decorator to register valid agent commands
def command(fn: Callable) -> Callable:
    # Verify all parameters (except self) have type annotations
    sig = inspect.signature(fn)
    for param_name, param in sig.parameters.items():
        if param_name != "self" and param.annotation == inspect.Parameter.empty:
            raise TypeError(f"Missing type annotation for parameter '{param_name}' in agent command '{fn.__name__}'")

    VALID_AGENT_COMMANDS[fn.__name__] = fn
    fn._agent_command = True
    return fn


from bbot.scanner.dispatcher import Dispatcher


class AgentDispatcher(Dispatcher):
    def __init__(self, agent, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.agent = agent

    async def on_status(self, status, scan_id):
        await self.agent.gratuitous_status_update(scan=self.scan, scan_status=status)


@async_to_sync_class
class BBOTAgent:
    """
    MUST-HAVE FEATURES
    - change log level (globally set on agent)
    - kill module mid scan
    - finish scan gracefully
    - forcefully stop scan
    - get full scan status (with detailed module status)
    """

    def __init__(self, id: str, name: str, config):
        self.log = logging.getLogger("bbot_server.agent")
        self.id = id
        self.name = name
        self.config = config
        self.server_url = config.url
        self.parsed_server_url = urlparse(self.server_url)
        self.websocket_scheme = "ws" if self.parsed_server_url.scheme == "http" else "wss"
        self.websocket_base_url = urlunparse(
            (
                self.websocket_scheme,
                self.parsed_server_url.netloc,
                self.parsed_server_url.path.rstrip("/") + "/",
                "",
                "",
                "",
            )
        )
        self.scan_output_url = urljoin(self.websocket_base_url, "events/")
        self.websocket_dock_url = urljoin(self.websocket_base_url, f"scans/agents/dock/{self.id}")
        self.websocket = None
        self.scan_task = None
        self.status = "READY"
        self.scan = None
        self._agent_preset = None
        self._agent_task = None

        self.dispatcher = AgentDispatcher(self)

    async def start(self):
        self.log.info(f"Starting agent {self.name} ({self.id})")
        self._agent_task = asyncio.create_task(self.loop())

    async def stop(self):
        if self._agent_task is None:
            return
        self._agent_task.cancel()
        with suppress(asyncio.CancelledError):
            await self._agent_task

    async def handle_message(self, message):
        command = message["command"]
        kwargs = message["kwargs"]
        if not isinstance(command, str) or not isinstance(kwargs, dict):
            raise BBOTServerValueError("Invalid message format")

        if command not in VALID_AGENT_COMMANDS:
            raise BBOTServerValueError(f"Invalid command: {command}")

        command_fn = getattr(self, command)
        return await command_fn(**kwargs)

    @command
    async def start_scan(self, scan_run: dict[str, Any]):
        if self.scan is not None:
            return {"status": "error", "message": "Scan already running"}
        scan_run = ScanRun(**scan_run)
        preset = self.make_agent_preset()
        preset.merge(Preset.from_dict(scan_run.preset))

        scan = Scanner(preset=preset, scan_id=scan_run.id, dispatcher=self.dispatcher)
        self._patch_scan(scan)
        self.scan_task = asyncio.create_task(self._start_scan_task(scan))
        return {"scan_id": scan.id, "scan_status": scan.status, "status": "success"}

    @command
    async def cancel_scan(self, force: bool = False):
        self.log.info(f"Cancelling scan with force={force}")
        if self.scan_task is None or self.scan_task.done() or self.scan_task.cancelled() or not self.scan:
            return {"status": "error", "message": "Scan not running"}
        if force:
            self.scan_task.cancel()
            # with suppress(asyncio.CancelledError):
            #     await self.scan_task
            return {"status": "success"}
        else:
            try:
                self.scan.stop()
            except Exception as e:
                self.log.error(f"Error stopping scan: {e}")
                self.log.error(traceback.format_exc())
            return {"status": "success"}

    async def _start_scan_task(self, scan):
        self.status = "BUSY"
        self.scan = scan
        await self.gratuitous_status_update()
        try:
            await scan.async_start_without_generator()
        except asyncio.CancelledError:
            self.log.warning("Scan cancelled")
        except BaseException as e:
            self.log.error(f"Error running scan: {e}")
            self.log.error(traceback.format_exc())
        finally:
            self.scan = None
            self.scan_task = None
            self.status = "READY"
            await self.gratuitous_status_update()

    @command
    async def get_agent_status(self, detailed: bool = False):
        ret = {"agent_status": self.status, "scan_status": getattr(self.scan, "status", "NOT_RUNNING")}
        if detailed and self.scan is not None:
            ret["scan_status_detail"] = self.scan.modules_status(detailed=detailed)
        return ret

    @command
    async def finish_scan(self):
        pass

    @command
    async def kill_module(self):
        pass

    @command
    async def get_file(self):
        pass

    def make_agent_preset(self):
        # default BBOT preset from bbot server YAML config
        default_preset = Preset.from_dict(default_bbot_preset)

        # agent-specific overrides for output url etc.
        agent_preset = Preset(
            output_modules=["http"],
            config={
                "modules": {
                    "http": {
                        "url": self.scan_output_url,
                    }
                }
            },
        )

        default_preset.merge(agent_preset)
        return default_preset

    async def loop(self):
        try:
            self.log.info(f"Agent {self.name} connecting to {self.websocket_dock_url}...")
            # "async for" will use websocket's builtin retry/reconnect mechanism, with exponential backoff
            # https://websockets.readthedocs.io/en/stable/reference/asyncio/client.html
            async for websocket in websockets.connect(self.websocket_dock_url):
                self.log.info(f"Agent {self.name} successfully connected to {self.websocket_dock_url}")
                self.websocket = websocket
                try:
                    # gratuitous status update on first connection
                    await self.gratuitous_status_update()

                    async for message in websocket:
                        message = orjson.loads(message)

                        try:
                            request_id = message.pop("request_id")
                            try:
                                command = message["command"]
                                kwargs = message["kwargs"]
                                if not isinstance(command, str) or not isinstance(kwargs, dict):
                                    raise BBOTServerValueError("Invalid message format")

                                if command not in VALID_AGENT_COMMANDS:
                                    raise BBOTServerValueError(f"Invalid command: {command}")

                                command_fn = getattr(self, command)
                                response = await command_fn(**kwargs)

                            except BaseException as e:
                                self.log.error(f"Error handling message: {e}")
                                self.log.error(traceback.format_exc())
                                raise
                            response = AgentResponse(request_id=request_id, response=response)

                        except Exception as e:
                            self.log.error(f"Error handling message: {e}")
                            trace = traceback.format_exc()
                            self.log.error(trace)
                            error = f"Error handling message: {e}\n{trace}"
                            response = AgentResponse(request_id=request_id, error=error)

                        self.log.info(f"Agent {self.name} sending response: {response}")
                        await websocket.send(orjson.dumps(response.model_dump()))

                except websockets.ConnectionClosed:
                    self.log.error("Connection closed, attempting to reconnect...")
                    await asyncio.sleep(1)
                except RuntimeError:
                    raise
                except Exception as e:
                    self.log.error(f"Unexpected error when connecting to {self.websocket_dock_url}: {e}")
                    self.log.error(traceback.format_exc())
                    await asyncio.sleep(1)  # Wait before retrying

        except asyncio.CancelledError:
            self.log.error("Agent loop cancelled")
        except RuntimeError as e:
            self.log.error(f"Unexpected error in agent loop: {e}")
        except BaseException as e:
            self.log.error(f"Unexpected error in agent loop: {e}")
            self.log.error(traceback.format_exc())
            raise

    async def gratuitous_status_update(self, scan=None, scan_status=None):
        scan_id = getattr(scan, "id", None)
        scan_name = getattr(scan, "name", None)
        scan_status = scan_status or getattr(scan, "status", "NOT_RUNNING")
        status = {
            "agent_status": self.status,
            "scan_status": scan_status,
            "scan_id": scan_id,
            "scan_name": scan_name,
        }
        if scan_id:
            try:
                status["scan_status_detail"] = scan.modules_status(detailed=True)
            except Exception as e:
                self.log.error(f"Error getting scan status detail: {e}")
                self.log.error(traceback.format_exc())
        agent_status = AgentResponse(response=status)
        await self.websocket.send(orjson.dumps(agent_status.model_dump()))

    def _patch_scan(self, scan):
        """
        Used by tests to patch the scan with DNS mocks, etc.
        """
        pass
