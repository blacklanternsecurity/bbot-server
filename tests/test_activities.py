def test_activities():
    from bbot_server.models.assets import AssetActivity

    activity = AssetActivity(type="TEST", description=f"New activity: [dark_orange]ACTIVITY[/dark_orange]")
    assert activity.description_colored == "New activity: [dark_orange]ACTIVITY[/dark_orange]"
    assert activity.description == "New activity: ACTIVITY"
