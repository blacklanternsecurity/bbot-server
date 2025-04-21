from bbot.modules.base import BaseModule


# module that pretends to be stuck
class Infinite(BaseModule):
    watched_events = ["*"]

    async def handle_event(self, event):
        try:
            self.log.critical(f"INFINITE HANDLING {event}")
            await self.helpers.sleep(99999999)
        finally:
            self.log.critical("INFINITE FINISHED")
