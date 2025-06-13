from tests.test_applets.base import BaseAppletTest


class TestArchival(BaseAppletTest):
    """
    This is a basic sanity check to make sure the event archiving process works as intended
    """

    needs_watchdog = True

    async def setup(self):
        events = [e async for e in self.bbot_server.get_events()]
        assert events == [], "events are not empty during setup"

    async def after_scan_1(self):
        archived_events = [e async for e in self.bbot_server.get_events(archived=True)]
        assert archived_events == [], "there are archived events after only the first scan"

        active_events = [e async for e in self.bbot_server.get_events(archived=False)]
        assert active_events, "there aren't any active events after the first scan"
        assert all(e.archived is False for e in active_events), "there are archived events after the first scan"

        all_events = [e async for e in self.bbot_server.get_events()]
        assert all_events, "there aren't any events after the first scan"
        assert len(all_events) == len(active_events), "some of the events appear to be archived after the first scan"

    async def after_scan_2(self):
        archived_events = [e async for e in self.bbot_server.get_events(archived=True)]
        assert archived_events == [], "there are archived events after the second scan"

        active_events = [e async for e in self.bbot_server.get_events(archived=False)]
        assert active_events, "there aren't any active events after the second scan"
        assert all(e.archived is False for e in active_events), "there are archived events after the second scan"

        all_events = [e async for e in self.bbot_server.get_events()]
        assert all(e.archived is False for e in all_events), "somehow an archived event got into the active events"

    async def after_archive(self):
        archived_events = [e async for e in self.bbot_server.get_events(archived=True)]
        active_events = [e async for e in self.bbot_server.get_events(archived=False)]
        all_events = [e async for e in self.bbot_server.get_events()]

        assert archived_events, "there aren't any archived events after the archival process"
        assert active_events, "there aren't any active events after the archival process"
        assert all_events, "there aren't any events after the archival process"

        assert all(e.archived is True for e in archived_events), (
            "somehow an unarchived event got into the archived ones"
        )
        assert all(e.archived is False for e in active_events), "somehow an archived event got into the active ones"
        assert len(all_events) == len(archived_events) + len(active_events), (
            "the archived + active events don't add up correctly"
        )
