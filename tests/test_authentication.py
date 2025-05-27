import httpx
import websockets
from omegaconf import OmegaConf

from .conftest import TEST_CONFIG_PATH


async def test_authentication(bbot_server_config, bbot_server_http):
    test_config = OmegaConf.load(TEST_CONFIG_PATH)
    api_key = test_config.api_key
    assert api_key, "API key is not set in test config"

    # basic request should fail with 403
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:8807/v1/assets/hosts")
        assert response.status_code == 403
    
    # streaming request should also fail
    async with httpx.AsyncClient() as client:
        async with client.stream("GET", f"http://localhost:8807/v1/events/list") as response:
            assert response.status_code == 403
            chunks = []
            async for chunk in response.aiter_bytes():
                chunks.append(chunk)
        assert chunks == [b'{"detail":"API Key is required"}']

    # websocket should also fail
    try:
        async with websockets.connect(f"ws://localhost:8807/v1/events/tail") as websocket:
            assert False, "Websocket should not connect without API key"
    except websockets.exceptions.InvalidStatusCode as e:
        assert e.status_code == 403

    # with valid API key, should succeed
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:8807/v1/assets/hosts", headers={"X-API-Key": api_key})
        assert response.status_code == 200
        assert response.json() == []
    
    # stream should succeed
    async with httpx.AsyncClient() as client:
        async with client.stream("GET", f"http://localhost:8807/v1/events/list", headers={"X-API-Key": api_key}) as response:
            assert response.status_code == 200
            events = [e async for e in response.aiter_bytes()]
            assert events == []

    # with invalid API key, should fail with 403
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:8807/v1/assets/hosts", headers={"X-API-Key": "invalid_api_key"})
        assert response.status_code == 403

    # test websocket connection with valid API key
    async with websockets.connect(f"ws://localhost:8807/v1/events/tail", additional_headers={"X-API-Key": api_key}) as websocket:
        # close websocket
        await websocket.close()
