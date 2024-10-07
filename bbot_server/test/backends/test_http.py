import httpx
import pytest

from . import IOTestBase


class TestHTTP(IOTestBase):
    needs_server = True
    backend = "http"
    kwargs = dict(url="http://127.0.0.1:7777")

    @pytest.mark.asyncio
    async def test_http_sanity_check(self, http_server, gen_scan_data):
        scan1_events, scan2_events = await gen_scan_data()

        # instantiate io module
        await self.setup()
        await self.ensure_empty()

        client = httpx.AsyncClient()

        events = (await client.get(f"{self.kwargs['url']}/events/")).json()
        assert isinstance(events, list)
        assert events == []

        for event in scan1_events:
            await client.post(f"{self.kwargs['url']}/events/", data=event.to_json())

        events = (await client.get(f"{self.kwargs['url']}/events/")).json()
        assert len(events) == 12
        assert any(e["data"] == {"DNS_NAME": "blacklanternsecurity.com"} for e in events)

        subdomains = (await client.get(f"{self.kwargs['url']}/subdomains/")).json()
        assert set(subdomains) == {
            "asdf.blacklanternsecurity.com",
            "blacklanternsecurity.com",
            "www.blacklanternsecurity.com",
        }

        await self.ensure_empty()
