async def test_applet_targets(bbot_server):
    bbot_server, watchdog, agent = await bbot_server()

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
    target = targets[0]
    assert target.name == "target1"
    assert target.id == target1.id
    assert target.description == "target1 description"
    assert target.target == ["localhost"]
    assert target.whitelist == ["127.0.0.1", "evilcorp.com"]
    assert target.blacklist == ["127.0.0.2"]

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
    target = targets[1]
    assert target.name == "target2"
    assert target.id == target2.id
    assert target.description == "target2 description"
    assert target.target == ["localhost"]
    assert target.whitelist == ["127.0.0.1", "evilcorp.com"]
    assert target.blacklist == ["127.0.0.2"]

    # delete target1
    await bbot_server.delete_target(target1.id)
    targets = await bbot_server.get_targets()
    assert len(targets) == 1
    target = targets[0]
    assert target.name == "target2"

    # edit target2
    target2.name = "target2_edited"
    target2.target = []
    target2.whitelist = []
    target2.blacklist = []
    await bbot_server.update_target(target2.id, target2)
    targets = await bbot_server.get_targets()
    assert len(targets) == 1
    target = targets[0]
    assert target.name == "target2_edited"
    assert target.target == []
    assert target.whitelist == []
    assert target.blacklist == []
