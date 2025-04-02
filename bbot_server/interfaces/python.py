from bbot_server.interfaces.base import BaseInterface
from bbot_server.utils.async_utils import async_to_sync_class


@async_to_sync_class
class python(BaseInterface):
    interface_type = "python"
