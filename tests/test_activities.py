def test_activities():
    from bbot_server.models.activity import Activity

    activity = Activity(type="TEST", description=f"New activity: [COLOR]ACTIVITY[/COLOR]")
    assert activity.description_colored == "New activity: [COLOR]ACTIVITY[/COLOR]"
    assert activity.description == "New activity: ACTIVITY"
