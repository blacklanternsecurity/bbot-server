from bbot_server import BBOTServer


async def test_asset_indexes(bbot_server_config):
    bbot_server = BBOTServer(config=bbot_server_config)
    await bbot_server.setup()

    assert bbot_server.assets.model.indexed_fields() == {
        "host": "indexed",
        "scope": "indexed",
        "created": "indexed",
        "modified": "indexed",
        "dns_links": "indexed",
        "open_ports": "indexed",
        "netloc": "indexed",
        "reverse_host": "indexed",
        "type": "indexed",
    }
    for applet in bbot_server.all_child_applets(include_self=True):
        if applet.model is not None:
            indexes = await applet.collection.list_indexes().to_list()
            indexed_fields = [list(idx["key"].keys())[0] for idx in indexes]
            for field in applet.model.indexed_fields():
                assert field in indexed_fields, (
                    f"{applet.name} (model: {applet.model.__name__}) has no index on {field}"
                )
