import pytest

from bbot_server.asset import Asset


@pytest.mark.asyncio
async def test_asset_modules(bbot_events):
    # assert len(bbot_events) == 21

    asset = Asset(host="127.0.0.1")
    print(asset)

    for event in bbot_events:
        asset.absorb_event(event)

    print(asset)
