from sqlmodel import Field
from pydantic import computed_field

from bbot_server.models.base import BaseHostModel, AssetQuery, derive
from bbot_server.utils.misc import utc_now


class TechnologyQuery(AssetQuery):
    """Base request body for technology query/count endpoints."""

    technology: str | None = Field(None, description="Filter by technology name")

    async def build(self, applet=None):
        stmt = await super().build(applet)
        model = self._applet.model

        if self.technology:
            stmt = stmt.where(model.technology == self.technology)

        return stmt


class Technology(BaseHostModel, table=True):
    __tablename__ = "technologies"

    pk: int | None = Field(default=None, primary_key=True)
    id: str | None = Field(default=None, index=True, sa_column_kwargs={"unique": True})
    technology: str = Field(index=True)
    last_seen: float = Field(default_factory=utc_now)

    @derive("id")
    def _derive_id(self):
        if self.technology and self.netloc:
            return self.sha1(f"{self.technology}:{self.netloc}")

    @computed_field
    @property
    def type(self) -> str:
        return "Technology"
