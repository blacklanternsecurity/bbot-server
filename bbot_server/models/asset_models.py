import re
from uuid import UUID
from typing import Optional, Annotated
from pydantic import Field, computed_field

from bbot_server.utils.misc import utc_now
from bbot.core.helpers.misc import make_netloc
from bbot_server.models.base import BaseBBOTServerModel

host_split_regex = re.compile(r"[^a-z0-9]")


class BaseHostModel(BaseBBOTServerModel):
    """
    A base model for all BBOT Server models that have a host, port, netloc, and url

    Inherited by Asset and Activity models.
    """

    # TODO: why is id commented out?
    # id: Annotated[str, "indexed", "unique"] = Field(default_factory=lambda: str(uuid.uuid4()))
    type: Annotated[Optional[str], "indexed"] = None
    host: Annotated[str, "indexed"]
    port: Annotated[Optional[int], "indexed"] = None
    netloc: Annotated[Optional[str], "indexed"] = None
    url: Annotated[Optional[str], "indexed"] = None
    created: Annotated[float, "indexed"] = Field(default_factory=utc_now)
    modified: Annotated[float, "indexed"] = Field(default_factory=utc_now)
    ignored: bool = False
    archived: bool = False

    def __init__(self, *args, **kwargs):
        event = kwargs.pop("event", None)
        super().__init__(*args, **kwargs)
        if self.host and self.port:
            self.netloc = make_netloc(self.host, self.port)
        if event is not None:
            self.set_event(event)

    def set_event(self, event):
        """
        Copy data from a BBOT event into the asset
        """
        if event.host and not self.host:
            self.host = event.host
        if event.port and not self.port:
            self.port = event.port
        if event.netloc and not self.netloc:
            self.netloc = event.netloc
        # handle url
        event_data_json = getattr(event, "data_json", None)
        if event_data_json is not None:
            url = event_data_json.get("url", None)
            if url is not None:
                self.url = url

    @computed_field
    @property
    def reverse_host(self) -> Annotated[str, "indexed"]:
        if not self.host:
            return ""
        return self.host[::-1]

    @computed_field
    @property
    def host_parts(self) -> Annotated[list[str], "indexed"]:
        if not self.host:
            return []
        return host_split_regex.split(self.host)


class BaseAssetFacet(BaseHostModel):
    """
    An "asset facet" is a database object that contains data about an asset.

    Unlike the main asset model which contains a summary of all the data,
    a facet contains a certain detail which is too big to be stored in the main asset model.

    For example, the main asset might contain a summary of all the technologies found on the asset,
    but a facet might contain the specific technologies and details about their discovery.

    A facet typically corresponds to an applet.
    """

    # scope is an array of target IDs, which are dynamically maintained as new scan data arrives, or as targets are created/updated.
    scope: Annotated[list[UUID], "indexed"] = []

    # unless overridden, all asset facets are stored in the asset store
    __store_type__ = "asset"
    __table_name__ = "assets"

    def __init__(self, *args, **kwargs):
        kwargs["type"] = self.__class__.__name__
        super().__init__(*args, **kwargs)
