from bbot.modules.base import BaseModule


# module that pretends to be stuck
class Infinite(BaseModule):
    watched_events = ["*"]

    async def handle_event(self, event):
        await self.helpers.sleep(99999999)
