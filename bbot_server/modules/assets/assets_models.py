from uuid import UUID
from sqlalchemy import select
from pydantic import Field

from bbot_server.models.base import HostQuery


class AssetOnlyQuery(HostQuery):
    """Query for the hosts lookup table. No archived/active filtering since Host is minimal."""

    target_id: str | UUID | None = Field(None, description="Filter by target name or ID")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_id = self.target_id or None
        if self.target_id is not None:
            self.target_id = str(self.target_id)

    async def build(self, applet=None):
        stmt = await super().build(applet)
        model = self._applet.model

        # target_id filtering via host_targets table
        if self.target_id is not None:
            from bbot_server.db.tables import HostTarget
            target_query_kwargs = {}
            if self.target_id != "DEFAULT":
                target_query_kwargs["id"] = self.target_id
            target = await self._applet.root.targets._get_target(**target_query_kwargs, fields=["id"])
            if target is not None:
                target_id = target["id"] if isinstance(target, dict) else target.id
                stmt = stmt.where(model.host.in_(
                    select(HostTarget.host).where(HostTarget.target_id == str(target_id))
                ))

        return stmt


class AdvancedAssetQuery(AssetOnlyQuery):
    """Advanced asset query with all AssetOnlyQuery features."""
    pass
