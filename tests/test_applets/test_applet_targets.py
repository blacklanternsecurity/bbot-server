async def test_applet_targets(bbot_server):
    from bbot_server.applets.targets import Target

    bbot_server = await bbot_server()

    targets = await bbot_server.get_targets()
    assert targets == []

    # create a target
    target1 = await bbot_server.create_target(
        name="target1",
        description="target1 description",
        target=["localhost"],
        whitelist=["127.0.0.1", "evilcorp.com"],
        blacklist=["127.0.0.2"],
    )

    targets = await bbot_server.get_targets()
    assert len(targets) == 1
    assert targets[0].name == "target1"
    assert targets[0].target == ["localhost"]
    assert targets[0].whitelist == ["127.0.0.1", "evilcorp.com"]
    assert targets[0].blacklist == ["127.0.0.2"]

    # create a second target
    target2 = await bbot_server.create_target(
        name="target2",
        description="target2 description",
        target=["localhost"],
        whitelist=["127.0.0.1", "evilcorp.com"],
        blacklist=["127.0.0.2"],
    )

    targets = await bbot_server.get_targets()
    assert len(targets) == 2
    assert targets[1].name == "target2"
    assert targets[1].target == ["localhost"]
    assert targets[1].whitelist == ["127.0.0.1", "evilcorp.com"]
    assert targets[1].blacklist == ["127.0.0.2"]

    # delete target1
    await bbot_server.delete_target(target1.id)
    targets = await bbot_server.get_targets()
    assert len(targets) == 1
    assert targets[0].name == "target2"

    # edit target2
    target2.name = "target2_edited"
    target2.target = []
    target2.whitelist = []
    target2.blacklist = []
    await bbot_server.update_target(target2.id, target2)
    targets = await bbot_server.get_targets()
    assert len(targets) == 1
    assert targets[0].name == "target2_edited"
    assert targets[0].target == []
    assert targets[0].whitelist == []
    assert targets[0].blacklist == []
