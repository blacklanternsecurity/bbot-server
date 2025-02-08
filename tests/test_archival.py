from tests.test_applets.base import BaseAppletTest


class TestArchival(BaseAppletTest):
    async def setup(self):
        events = [e async for e in self.bbot_server.get_events(archived=None)]
        assert events == [], "events are not empty during setup"

    async def after_scan_1(self):
        archived_events = [e async for e in self.bbot_server.get_events(archived=True)]
        assert archived_events == [], "there are archived events after only the first scan"

        active_events = [e async for e in self.bbot_server.get_events(archived=False)]
        assert active_events, "there aren't any active events after the first scan"
        assert all(e.archived is False for e in active_events), "there are archived events after the first scan"

        all_events = [e async for e in self.bbot_server.get_events(archived=None)]
        assert all_events, "there aren't any events after the first scan"
        assert len(all_events) == len(active_events), "some of the events appear to be archived after the first scan"

    async def after_scan_2(self):
        archived_events = [e async for e in self.bbot_server.get_events(archived=True)]
        assert archived_events == []

        active_events = [e async for e in self.bbot_server.get_events(archived=False)]
        assert active_events
        assert all(e.archived is False for e in active_events)

    async def after_archive(self):
        archived_events = [e async for e in self.bbot_server.get_events(archived=True)]
        active_events = [e async for e in self.bbot_server.get_events(archived=False)]
        all_events = [e async for e in self.bbot_server.get_events(archived=None)]

        assert archived_events
        assert active_events
        assert all_events

        assert all(e.archived is True for e in archived_events)
        assert all(e.archived is False for e in active_events)
        assert len(all_events) == len(archived_events) + len(active_events)
