import httpx
import logging
from functools import partialmethod

from bbot_io.interfaces._base import BaseInterface


log = logging.getLogger("bbot.io.rest")


class RestInterface(BaseInterface):

    def __init__(self, applet, url):
        super().__init__(applet)
        self.base_url = url
        self.client = httpx.AsyncClient()

    async def _request(self, fn, *args, **kwargs):
        url = f"{self.base_url}/{fn.__name__}"
        log.critical(f"{url} / {args} / {kwargs}")

    def __getattr__(self, attr):
        fn = getattr(self.applet, attr)
        return partialmethod(self._request, fn)
