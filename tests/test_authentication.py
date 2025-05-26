import httpx
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

    # with valid API key, should succeed
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:8807/v1/assets/hosts", headers={"X-API-Key": api_key})
        assert response.status_code == 200
        assert response.json() == []

    # with invalid API key, should fail with 403
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:8807/v1/assets/hosts", headers={"X-API-Key": "invalid_api_key"})
        assert response.status_code == 403
