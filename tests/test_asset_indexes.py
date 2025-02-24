async def test_asset_indexes(bbot_server):
    bbot_server = await bbot_server()

    assert bbot_server.assets.open_ports.model.indexed_fields() == {
        "host": "indexed",
        "open_ports": "indexed",
        "reverse_host": "indexed",
        "type": "indexed",
    }
    for applet in bbot_server.all_child_applets:
        if applet.model is not None:
            indexes = await applet.collection.list_indexes().to_list()
            indexed_fields = [list(idx["key"].keys())[0] for idx in indexes]
            for field in applet.model.indexed_fields():
                assert field in indexed_fields, (
                    f"{applet.name} (model: {applet.model.__name__}) has no index on {field}"
                )
