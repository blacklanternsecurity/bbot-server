import httpx


async def test_authentication(bbot_server_config, bbot_server_http):
    # basic request should fail with 403
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:8807/v1/assets/hosts")
        assert response.status_code == 403

    # with valid API key, should succeed
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:8807/v1/assets/hosts", headers={"X-API-Key": "test_api_key"})
        assert response.status_code == 200
        assert response.json() == []

    # with invalid API key, should fail with 403
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:8807/v1/assets/hosts", headers={"X-API-Key": "invalid_api_key"})
        assert response.status_code == 403
