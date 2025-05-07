from bbot_server import BBOTServer


async def test_asset_indexes(bbot_server_config):
    bbot_server = BBOTServer(config=bbot_server_config)
    await bbot_server.setup()

    assert bbot_server.assets.model.indexed_fields() == {
        "host": ["indexed"],
        "scope": ["indexed"],
        "created": ["indexed"],
        "modified": ["indexed"],
        "dns_links": ["indexed"],
        "open_ports": ["indexed"],
        "netloc": ["indexed"],
        "reverse_host": ["indexed"],
        "type": ["indexed"],
        "port": ["indexed"],
        "technologies": ["indexed", "indexed-text"],
        "url": ["indexed"],
        "cloud_providers": ["indexed"],
        "findings": ["indexed", "indexed-text"],
        "finding_max_severity_score": ["indexed"],
        "finding_severities": ["indexed"],
    }
    for applet in bbot_server.all_child_applets(include_self=True):
        if applet.model is not None:
            indexes = await applet.collection.list_indexes().to_list()
            indexed_fields = []
            for idx in indexes:
                # Handle text indexes specially
                if "_fts" in idx["key"] and "_ftsx" in idx["key"]:
                    # For text indexes, the field name is in the weights
                    if "weights" in idx:
                        indexed_fields.extend(idx["weights"].keys())
                else:
                    # For regular indexes, get the first key
                    indexed_fields.extend(idx["key"].keys())

            for field in applet.model.indexed_fields():
                assert field in indexed_fields, (
                    f"{applet.name} (model: {applet.model.__name__}) has no index on {field}. indexes: {indexes}"
                )
