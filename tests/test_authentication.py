import uuid
import httpx
import websockets
from omegaconf import OmegaConf

from .conftest import TEST_CONFIG_PATH


async def test_authentication(bbot_server_config, bbot_server_http):
    test_config = OmegaConf.load(TEST_CONFIG_PATH)
    api_keys = test_config.get("api_keys", [])
    assert len(api_keys) == 1, "API keys are not set in test config"
    api_key = api_keys[0]

    ## NO API KEY ##

    # basic request should fail with 401
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:8807/v1/assets/hosts")
        assert response.status_code == 401

    # streaming request should also fail
    async with httpx.AsyncClient() as client:
        async with client.stream("GET", f"http://localhost:8807/v1/events/list") as response:
            assert response.status_code == 401
            chunks = []
            async for chunk in response.aiter_bytes():
                chunks.append(chunk)
        assert chunks == [b'{"detail":"API key is required"}']

    # websocket should also fail
    try:
        async with websockets.connect(f"ws://localhost:8807/v1/agent/dock/{uuid.uuid4()}") as websocket:
            assert False, "Websocket should not connect without API key"
    except websockets.exceptions.InvalidStatus as e:
        assert e.response.status_code == 403

    # same for outgoing websocket
    try:
        async with websockets.connect(f"ws://localhost:8807/v1/events/tail") as websocket:
            assert False, "Websocket should not connect without API key"
    except websockets.exceptions.InvalidStatus as e:
        assert e.response.status_code == 403

    # same for incoming websocket
    try:
        async with websockets.connect(f"ws://localhost:8807/v1/events/ingest") as websocket:
            assert False, "Websocket should not connect without API key"
    except websockets.exceptions.InvalidStatus as e:
        assert e.response.status_code == 403

    ## VALID API KEY ##

    # with valid API key, should succeed
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:8807/v1/assets/hosts", headers={"X-API-Key": api_key})
        assert response.status_code == 200
        assert response.json() == []

    # stream should succeed
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "GET", f"http://localhost:8807/v1/events/list", headers={"X-API-Key": api_key}
        ) as response:
            assert response.status_code == 200
            events = [e async for e in response.aiter_bytes()]
            assert events == []

    # websocket outgoing should succeed
    async with websockets.connect(
        f"ws://localhost:8807/v1/events/tail", additional_headers={"X-API-Key": api_key}
    ) as websocket:
        assert websocket.response.status_code == 101
        await websocket.close()

    # websocket incoming
    async with websockets.connect(
        f"ws://localhost:8807/v1/events/ingest", additional_headers={"X-API-Key": api_key}
    ) as websocket:
        assert websocket.response.status_code == 101
        # close websocket
        await websocket.close()

    # with invalid API key, should fail with 401
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:8807/v1/assets/hosts", headers={"X-API-Key": "invalid_api_key"})
        assert response.status_code == 401

    # test websocket connection with valid API key
    async with websockets.connect(
        f"ws://localhost:8807/v1/events/tail", additional_headers={"X-API-Key": api_key}
    ) as websocket:
        # close websocket
        await websocket.close()
