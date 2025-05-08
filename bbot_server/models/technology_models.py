from pydantic import Field
from typing import Annotated
from pydantic import computed_field

from bbot_server.utils.misc import utc_now
from bbot_server.models.asset_models import BaseAssetFacet


class Technology(BaseAssetFacet):
    technology: Annotated[str, "indexed", "indexed-text"]
    last_seen: Annotated[float, "indexed"] = Field(default_factory=utc_now)

    @computed_field
    @property
    def id(self) -> Annotated[str, "indexed", "unique"]:
        """We dedupe technologies by technology+netloc"""
        return self.sha1(f"{self.technology}:{self.netloc}")
