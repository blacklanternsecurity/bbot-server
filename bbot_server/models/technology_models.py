from pydantic import Field
from typing import Annotated

from bbot_server.utils.misc import utc_now
from bbot_server.models.asset_models import BaseAssetFacet


class Technology(BaseAssetFacet):
    # unique compound index on technology+host+port makes sure we don't have duplicates
    technology: Annotated[str, "indexed-compound:host,port", "indexed-text", "unique"]
    last_seen: Annotated[float, "indexed"] = Field(default_factory=utc_now)
