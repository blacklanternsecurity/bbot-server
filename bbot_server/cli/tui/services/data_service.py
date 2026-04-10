"""Data service for BBOT Server TUI"""

import logging
from typing import Optional, List, Any

from bbot_server.errors import BBOTServerError, BBOTServerUnauthorizedError


log = logging.getLogger(__name__)


class DataService:
    def __init__(self, bbot_server):
        self.bbot_server = bbot_server
        if hasattr(bbot_server, "_instance"):
            self._async_client = bbot_server._instance
            log.debug("Using native async client via ._instance")
        else:
            self._async_client = bbot_server
            log.warning("._instance not found, using sync wrapper as fallback")

    async def _fetch_paginated(
        self, query_method: str, count_method: str, skip: int = 0, limit: int = 25, **filters
    ) -> tuple[List[Any], int]:
        kwargs = {k: v for k, v in filters.items() if v is not None}
        try:
            query_fn = getattr(self._async_client, query_method)
            items = [item async for item in query_fn(skip=skip, limit=limit, **kwargs)]
            count_fn = getattr(self._async_client, count_method)
            total = await count_fn(**kwargs)
            log.debug(f"Fetched {len(items)} items (skip={skip}, limit={limit}, total={total})")
            return items, total
        except BBOTServerUnauthorizedError:
            raise
        except BBOTServerError:
            log.exception(f"Error in {query_method}")
            return [], 0
        except Exception:
            log.exception(f"Unexpected error in {query_method}")
            return [], 0

    async def get_scans(self) -> List[Any]:
        try:
            scans = [scan async for scan in self._async_client.get_scans()]
            log.debug(f"Fetched {len(scans)} scans")
            return scans
        except BBOTServerUnauthorizedError:
            raise
        except BBOTServerError:
            log.exception("Error fetching scans")
            return []

    async def get_assets_paginated(self, skip: int = 0, limit: int = 25, **filters) -> tuple[List[Any], int]:
        return await self._fetch_paginated("query_assets", "count_assets", skip, limit, **filters)

    async def get_findings_paginated(self, skip: int = 0, limit: int = 25, **filters) -> tuple[List[Any], int]:
        return await self._fetch_paginated("query_findings", "count_findings", skip, limit, **filters)

    async def get_events_paginated(self, skip: int = 0, limit: int = 25, **filters) -> tuple[List[Any], int]:
        return await self._fetch_paginated("query_events", "count_events", skip, limit, **filters)

    async def get_scans_paginated(self, skip: int = 0, limit: int = 25, **filters) -> tuple[List[Any], int]:
        return await self._fetch_paginated("query_scans", "count_scans", skip, limit, **filters)

    async def get_technologies_paginated(self, skip: int = 0, limit: int = 25, **filters) -> tuple[List[Any], int]:
        return await self._fetch_paginated("query_technologies", "count_technologies", skip, limit, **filters)

    async def get_targets_paginated(self, skip: int = 0, limit: int = 25, **filters) -> tuple[List[Any], int]:
        return await self._fetch_paginated("query_targets", "count_targets", skip, limit, **filters)

    async def create_target(
        self,
        name: str,
        description: str = "",
        target: Optional[List[str]] = None,
        seeds: Optional[List[str]] = None,
        blacklist: Optional[List[str]] = None,
        strict_scope: bool = False,
    ) -> Optional[Any]:
        try:
            target_data = {
                "name": name,
                "description": description,
                "target": target or [],
                "blacklist": blacklist or [],
                "strict_scope": strict_scope,
            }
            if seeds is not None:
                target_data["seeds"] = seeds
            log.info(f"Creating target: {name}")
            created_target = await self._async_client.create_target(**target_data)
            log.info(f"Created target: {name}")
            return created_target
        except BBOTServerError:
            log.exception("Error creating target")
            raise

    async def update_target(
        self,
        target_id: str,
        name: str,
        description: str = "",
        target: Optional[List[str]] = None,
        seeds: Optional[List[str]] = None,
        blacklist: Optional[List[str]] = None,
        strict_scope: bool = False,
    ) -> Optional[Any]:
        try:
            from bbot_server.modules.targets.targets_models import Target as TargetModel

            target_data = {
                "name": name,
                "description": description,
                "target": target or [],
                "blacklist": blacklist or [],
                "strict_scope": strict_scope,
            }
            if seeds is not None:
                target_data["seeds"] = seeds
            log.info(f"Updating target {target_id}: {name}")
            target_model = TargetModel(**target_data)
            updated_target = await self._async_client.update_target(id=target_id, target=target_model)
            log.info(f"Updated target: {name}")
            return updated_target
        except BBOTServerError:
            log.exception("Error updating target")
            raise

    async def delete_target(self, target_id: str) -> None:
        try:
            log.info(f"Deleting target {target_id}")
            await self._async_client.delete_target(id=target_id)
            log.info(f"Deleted target: {target_id}")
        except BBOTServerError:
            log.exception("Error deleting target")
            raise
