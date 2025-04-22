def test_activities():
    from bbot_server.models.activity_models import Activity

    activity = Activity(type="TEST", description=f"New activity: [COLOR]ACTIVITY[/COLOR]")
    assert activity.description_colored == "New activity: [bold dark_orange]ACTIVITY[/bold dark_orange]"
    assert activity.description == "New activity: ACTIVITY"
