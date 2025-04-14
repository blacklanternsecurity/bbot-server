def test_activities():
    from bbot_server.models.activity import Activity

    activity = Activity(type="TEST", description=f"New activity: [dark_orange]ACTIVITY[/dark_orange]")
    assert activity.description_colored == "New activity: [dark_orange]ACTIVITY[/dark_orange]"
    assert activity.description == "New activity: ACTIVITY"
