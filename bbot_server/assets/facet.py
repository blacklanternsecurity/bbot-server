from pydantic import Field
from typing import Optional, Union, Annotated

from bbot_server.utils.misc import utc_now
from bbot_server.models.base import BaseBBOTServerModel


class BaseAssetFacet(BaseBBOTServerModel):
    """
    An "asset facet" is a database object that contains data about an asset.

    Unlike the main asset model which contains a summary of all the data,
    a facet contains a certain detail which is too big to be stored in the main asset model.

    For example, the main asset might contain a summary of all the technologies found on the asset,
    but a facet might contain the specific technologies and details about their discovery.

    A facet typically corresponds to an applet.
    """

    host: Annotated[str, "indexed"]
    type: Annotated[Optional[str], "indexed"] = None
    reverse_host: Annotated[Optional[Union[str, None]], "indexed"] = None
    netloc: Annotated[Optional[Union[str, None]], "indexed"] = None
    created: Annotated[float, "indexed"] = Field(default_factory=utc_now)
    modified: Annotated[float, "indexed"] = Field(default_factory=utc_now)
    ignored: bool = False
    archived: bool = False

    def __init__(self, *args, **kwargs):
        kwargs["type"] = self.__class__.__name__
        super().__init__(*args, **kwargs)

    # def _ingest_event(self, event) -> list[Activity]:
    #     self_before = self.__class__.model_validate(self)
    #     self.ingest_event(event)
    #     return self.diff(self_before)

    # def ingest_event(self, event):
    #     """
    #     Given a BBOT event, update the asset facet.

    #     E.g., given an OPEN_TCP_PORT event, update the open_ports field to include the new port.
    #     """
    #     raise NotImplementedError(f"Must define ingest_event() in {self.__class__.__name__}")

    # def diff(self, other) -> list[Activity]:
    #     """
    #     Given another facet (typically an older version of the same host), return a list of AssetActivities which describe the new changes.
    #     """
    #     raise NotImplementedError(f"Must define diff() in {self.__class__.__name__}")
