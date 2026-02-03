"""
Data service for BBOT Server TUI

Wraps the BBOTServer HTTP client and provides convenient methods
for fetching data with error handling.
"""
import logging
from typing import Optional, List, Any

from bbot_server.errors import BBOTServerError, BBOTServerNotFoundError, BBOTServerUnauthorizedError


log = logging.getLogger(__name__)


class DataService:
    """
    Service for fetching data from BBOT Server

    Wraps the BBOTServer HTTP client with error handling and convenience methods
    for the TUI application.
    """

    def __init__(self, bbot_server):
        """
        Initialize the data service

        Args:
            bbot_server: BBOTServer HTTP client instance (sync wrapper)
        """
        self.bbot_server = bbot_server

        # Get the underlying async client from the sync wrapper
        # This gives us native async methods without sync conversion overhead
        if hasattr(bbot_server, '_instance'):
            self._async_client = bbot_server._instance
            log.debug("Using native async client via ._instance")
        else:
            # Fallback: use the sync wrapper
            self._async_client = bbot_server
            log.warning("._instance not found, using sync wrapper as fallback")

    async def _fetch_paginated(
        self,
        query_method: str,
        count_method: str,
        skip: int = 0,
        limit: int = 25,
        **filters
    ) -> tuple[List[Any], int]:
        """
        Generic paginated fetch with count

        Calls the query endpoint for items and count endpoint for total.
        Both endpoints accept the same Query model, ensuring filter consistency.

        Args:
            query_method: Name of the async generator method (e.g., 'query_assets')
            count_method: Name of the count method (e.g., 'count_assets')
            skip: Number of items to skip
            limit: Maximum items to return
            **filters: Query filters (search, domain, target_id, etc.)

        Returns:
            Tuple of (items list, total count)
        """
        # Filter out None values
        kwargs = {k: v for k, v in filters.items() if v is not None}

        try:
            # Get items via streaming query
            query_fn = getattr(self._async_client, query_method)
            items = [item async for item in query_fn(skip=skip, limit=limit, **kwargs)]

            # Get total count (same filters, no skip/limit)
            count_fn = getattr(self._async_client, count_method)
            total = await count_fn(**kwargs)

            log.debug(f"Fetched {len(items)} items (skip={skip}, limit={limit}, total={total})")
            return items, total
        except BBOTServerUnauthorizedError:
            raise
        except BBOTServerError as e:
            log.error(f"Error in {query_method}: {e}")
            return [], 0

    async def get_assets_paginated(
        self,
        skip: int = 0,
        limit: int = 25,
        **filters
    ) -> tuple[List[Any], int]:
        """
        Fetch assets with pagination and total count

        Args:
            skip: Number of items to skip
            limit: Maximum items to return
            **filters: Query filters (search, domain, target_id, host)

        Returns:
            Tuple of (assets list, total count)
        """
        return await self._fetch_paginated('query_assets', 'count_assets', skip, limit, **filters)

    async def get_scans(self, skip: int = 0, limit: Optional[int] = None) -> List[Any]:
        """
        Fetch all scans

        Args:
            skip: Number of scans to skip (for pagination)
            limit: Maximum number of scans to return (None = all)

        Returns:
            List of Scan models
        """
        try:
            # Use native async generator from the async client
            scans = [scan async for scan in self._async_client.get_scans()]
            log.debug(f"Fetched {len(scans)} scans")
            # Apply skip and limit client-side
            if limit is not None:
                return scans[skip:skip + limit]
            return scans[skip:]
        except BBOTServerUnauthorizedError as e:
            log.error(f"Authentication failed: {e}")
            raise
        except BBOTServerError as e:
            log.error(f"Error fetching scans: {e}")
            return []

    async def get_scan(self, scan_id: str) -> Optional[Any]:
        """
        Fetch a specific scan by ID

        Args:
            scan_id: Scan identifier

        Returns:
            Scan model or None if not found
        """
        try:
            scan = await self._async_client.get_scan(scan_id)
            return scan
        except BBOTServerNotFoundError:
            log.warning(f"Scan not found: {scan_id}")
            return None
        except BBOTServerError as e:
            log.error(f"Error fetching scan {scan_id}: {e}")
            return None

    async def list_assets(self, domain: Optional[str] = None, target_id: Optional[str] = None,
                         limit: int = 1000, skip: int = 0) -> List[Any]:
        """
        Fetch assets with optional filters

        Args:
            domain: Filter by domain (includes subdomains)
            target_id: Filter by target ID
            limit: Maximum number of assets to return
            skip: Number of assets to skip (for pagination)

        Returns:
            List of Asset models
        """
        try:
            kwargs = {}
            if domain:
                kwargs['domain'] = domain
            if target_id:
                kwargs['target_id'] = target_id

            assets = [asset async for asset in self._async_client.list_assets(**kwargs)]
            log.debug(f"Fetched {len(assets)} assets")
            # Apply skip and limit client-side
            return assets[skip:skip + limit]
        except BBOTServerError as e:
            log.error(f"Error fetching assets: {e}")
            return []

    async def query_assets(self, domain: Optional[str] = None, target_id: Optional[str] = None,
                          host: Optional[str] = None, search: Optional[str] = None,
                          limit: int = 1000, skip: int = 0) -> List[Any]:
        """
        Query assets with advanced filters and pagination

        Args:
            domain: Filter by domain (includes subdomains)
            target_id: Filter by target ID
            host: Filter by exact host
            search: Search term
            limit: Maximum number of assets to return
            skip: Number of assets to skip (for pagination)

        Returns:
            List of Asset models
        """
        try:
            kwargs = {}
            if domain:
                kwargs['domain'] = domain
            if target_id:
                kwargs['target_id'] = target_id
            if host:
                kwargs['host'] = host
            if search:
                kwargs['search'] = search
            if limit:
                kwargs['limit'] = limit
            if skip:
                kwargs['skip'] = skip

            assets = [asset async for asset in self._async_client.query_assets(**kwargs)]
            log.debug(f"Fetched {len(assets)} assets (skip={skip}, limit={limit})")
            return assets
        except BBOTServerError as e:
            log.error(f"Error querying assets: {e}")
            return []

    async def get_asset(self, host: str) -> Optional[Any]:
        """
        Fetch a specific asset by host

        Args:
            host: Hostname or IP address

        Returns:
            Asset model or None if not found
        """
        try:
            asset = await self._async_client.get_asset(host)
            return asset
        except BBOTServerNotFoundError:
            log.warning(f"Asset not found: {host}")
            return None
        except BBOTServerError as e:
            log.error(f"Error fetching asset {host}: {e}")
            return None

    async def list_findings(self, host: Optional[str] = None, domain: Optional[str] = None,
                           target_id: Optional[str] = None, search: Optional[str] = None,
                           min_severity: Optional[int] = None, max_severity: Optional[int] = None,
                           limit: int = 1000, skip: int = 0) -> List[Any]:
        """
        Fetch findings with optional filters

        Args:
            host: Filter by exact host
            domain: Filter by domain
            target_id: Filter by target ID
            search: Search in name/description
            min_severity: Minimum severity (1-5)
            max_severity: Maximum severity (1-5)
            limit: Maximum number of findings to return
            skip: Number of findings to skip (for pagination)

        Returns:
            List of Finding models
        """
        try:
            kwargs = {}
            if host:
                kwargs['host'] = host
            if domain:
                kwargs['domain'] = domain
            if target_id:
                kwargs['target_id'] = target_id
            if search:
                kwargs['search'] = search
            if min_severity:
                kwargs['min_severity'] = min_severity
            if max_severity:
                kwargs['max_severity'] = max_severity

            findings = [finding async for finding in self._async_client.list_findings(**kwargs)]
            log.debug(f"Fetched {len(findings)} findings")
            # Apply skip and limit client-side
            return findings[skip:skip + limit]
        except BBOTServerError as e:
            log.error(f"Error fetching findings: {e}")
            return []

    async def query_findings(self, host: Optional[str] = None, domain: Optional[str] = None,
                            target_id: Optional[str] = None, search: Optional[str] = None,
                            min_severity: Optional[int] = None, max_severity: Optional[int] = None,
                            limit: int = 1000, skip: int = 0) -> List[Any]:
        """
        Query findings with advanced filters and pagination

        Args:
            host: Filter by exact host
            domain: Filter by domain
            target_id: Filter by target ID
            search: Search term
            min_severity: Minimum severity (1-5)
            max_severity: Maximum severity (1-5)
            limit: Maximum number of findings to return
            skip: Number of findings to skip (for pagination)

        Returns:
            List of Finding models
        """
        try:
            kwargs = {}
            if host:
                kwargs['host'] = host
            if domain:
                kwargs['domain'] = domain
            if target_id:
                kwargs['target_id'] = target_id
            if search:
                kwargs['search'] = search
            if min_severity:
                kwargs['min_severity'] = min_severity
            if max_severity:
                kwargs['max_severity'] = max_severity
            if limit:
                kwargs['limit'] = limit
            if skip:
                kwargs['skip'] = skip
            # Keep default sort by severity
            kwargs['sort'] = [("severity_score", -1)]

            findings = [finding async for finding in self._async_client.query_findings(**kwargs)]
            log.debug(f"Fetched {len(findings)} findings (skip={skip}, limit={limit})")
            return findings
        except BBOTServerError as e:
            log.error(f"Error querying findings: {e}")
            return []

    async def list_activities(self, host: Optional[str] = None, activity_type: Optional[str] = None,
                             limit: int = 100) -> List[Any]:
        """
        Fetch activities with optional filters

        Args:
            host: Filter by exact host
            activity_type: Filter by activity type (e.g., NEW_FINDING, NEW_ASSET)
            limit: Maximum number of activities to return

        Returns:
            List of Activity models
        """
        try:
            kwargs = {}
            if host:
                kwargs['host'] = host
            if activity_type:
                kwargs['type'] = activity_type

            activities = [activity async for activity in self._async_client.list_activities(**kwargs)]
            log.debug(f"Fetched {len(activities)} activities")
            # Apply skip and limit client-side
            return activities[skip:skip + limit]
        except BBOTServerError as e:
            log.error(f"Error fetching activities: {e}")
            return []

    async def get_stats(self) -> dict:
        """
        Fetch aggregate statistics

        Returns:
            Dictionary with stats (scan_count, asset_count, finding_count, etc.)
        """
        try:
            stats = await self._async_client.get_stats()
            log.debug(f"Fetched stats: {stats}")
            return stats
        except BBOTServerError as e:
            log.error(f"Error fetching stats: {e}")
            return {
                'scan_count': 0,
                'active_scan_count': 0,
                'asset_count': 0,
                'finding_count': 0,
            }

    async def get_targets(self, skip: int = 0, limit: Optional[int] = None) -> List[Any]:
        """
        Fetch all targets

        Args:
            skip: Number of targets to skip (for pagination)
            limit: Maximum number of targets to return (None = all)

        Returns:
            List of Target models
        """
        try:
            targets = await self._async_client.get_targets()
            log.debug(f"Fetched {len(targets)} targets")
            # Apply skip and limit client-side
            if limit is not None:
                return targets[skip:skip + limit]
            return targets[skip:]
        except BBOTServerError as e:
            log.error(f"Error fetching targets: {e}")
            return []

    async def get_presets(self) -> List[Any]:
        """
        Fetch all presets

        Returns:
            List of Preset models
        """
        try:
            presets = await self._async_client.get_presets()
            log.debug(f"Fetched {len(presets)} presets")
            return presets
        except BBOTServerError as e:
            log.error(f"Error fetching presets: {e}")
            return []

    async def list_events(self, event_type: Optional[str] = None, host: Optional[str] = None,
                         domain: Optional[str] = None, scan: Optional[str] = None,
                         active: bool = True, archived: bool = False,
                         limit: int = 1000, skip: int = 0) -> List[Any]:
        """
        List BBOT events with optional filters

        Args:
            event_type: Filter by event type
            host: Filter by exact hostname or IP
            domain: Filter by domain (including subdomains)
            scan: Filter by scan ID
            active: Include active (non-archived) events
            archived: Include archived events
            limit: Maximum number of events to return
            skip: Number of events to skip (for pagination)

        Returns:
            List of Event models
        """
        try:
            kwargs = {}
            if event_type:
                kwargs['type'] = event_type
            if host:
                kwargs['host'] = host
            if domain:
                kwargs['domain'] = domain
            if scan:
                kwargs['scan'] = scan
            kwargs['active'] = active
            kwargs['archived'] = archived

            # NOTE: list_events API doesn't support skip/limit, so we fetch all and slice
            # For large datasets, this will be slow on first load
            events = [event async for event in self._async_client.list_events(**kwargs)]
            log.debug(f"Fetched {len(events)} events")
            # Apply skip and limit client-side
            return events[skip:skip + limit]
        except BBOTServerError as e:
            log.error(f"Error fetching events: {e}")
            return []

    async def query_events(self, host: Optional[str] = None, domain: Optional[str] = None,
                          target_id: Optional[str] = None, search: Optional[str] = None,
                          active: bool = True, archived: bool = False,
                          min_timestamp: Optional[float] = None, max_timestamp: Optional[float] = None,
                          limit: int = 1000, skip: int = 0) -> List[Any]:
        """
        Query events with advanced filters and pagination

        Args:
            host: Filter by exact hostname or IP
            domain: Filter by domain (includes subdomains)
            target_id: Filter by target ID
            search: Search term
            active: Include active (non-archived) events
            archived: Include archived events
            min_timestamp: Filter by minimum timestamp
            max_timestamp: Filter by maximum timestamp
            limit: Maximum number of events to return
            skip: Number of events to skip (for pagination)

        Returns:
            List of event dictionaries
        """
        try:
            kwargs = {}
            if host:
                kwargs['host'] = host
            if domain:
                kwargs['domain'] = domain
            if target_id:
                kwargs['target_id'] = target_id
            if search:
                kwargs['search'] = search
            if min_timestamp is not None:
                kwargs['min_timestamp'] = min_timestamp
            if max_timestamp is not None:
                kwargs['max_timestamp'] = max_timestamp
            kwargs['active'] = active
            kwargs['archived'] = archived
            if limit:
                kwargs['limit'] = limit
            if skip:
                kwargs['skip'] = skip

            events = [event async for event in self._async_client.query_events(**kwargs)]
            log.debug(f"Fetched {len(events)} events (skip={skip}, limit={limit})")
            return events
        except BBOTServerError as e:
            log.error(f"Error querying events: {e}")
            return []

    async def list_technologies(self, domain: Optional[str] = None, host: Optional[str] = None,
                               technology: Optional[str] = None, search: Optional[str] = None,
                               target_id: Optional[str] = None, limit: int = 1000, skip: int = 0) -> List[Any]:
        """
        List technologies with optional filters

        Args:
            domain: Filter by domain (includes subdomains)
            host: Filter by exact host
            technology: Filter by technology name (exact match)
            search: Search in technology names
            target_id: Filter by target ID
            limit: Maximum number of technologies to return
            skip: Number of technologies to skip (for pagination)

        Returns:
            List of Technology models
        """
        try:
            kwargs = {}
            if domain:
                kwargs['domain'] = domain
            if host:
                kwargs['host'] = host
            if technology:
                kwargs['technology'] = technology
            if search:
                kwargs['search'] = search
            if target_id:
                kwargs['target_id'] = target_id

            # NOTE: list_technologies API doesn't support skip/limit, so we fetch all and slice
            # For large datasets, this will be slow on first load
            technologies = [tech async for tech in self._async_client.list_technologies(**kwargs)]
            log.debug(f"Fetched {len(technologies)} technologies")
            # Apply skip and limit client-side
            return technologies[skip:skip + limit]
        except BBOTServerError as e:
            log.error(f"Error fetching technologies: {e}")
            return []

    async def get_findings_paginated(
        self,
        skip: int = 0,
        limit: int = 25,
        **filters
    ) -> tuple[List[Any], int]:
        """
        Fetch findings with pagination and total count

        Args:
            skip: Number of items to skip
            limit: Maximum items to return
            **filters: Query filters (search, domain, target_id, host, min_severity, max_severity)

        Returns:
            Tuple of (findings list, total count)
        """
        return await self._fetch_paginated('query_findings', 'count_findings', skip, limit, **filters)

    async def get_events_paginated(
        self,
        skip: int = 0,
        limit: int = 25,
        **filters
    ) -> tuple[List[Any], int]:
        """
        Fetch events with pagination and total count

        Args:
            skip: Number of items to skip
            limit: Maximum items to return
            **filters: Query filters (search, domain, target_id, host, active, archived)

        Returns:
            Tuple of (events list, total count)
        """
        return await self._fetch_paginated('query_events', 'count_events', skip, limit, **filters)

    async def get_scans_paginated(
        self,
        skip: int = 0,
        limit: int = 25,
        filter_text: Optional[str] = None
    ) -> tuple[List[Any], int]:
        """
        Fetch scans with client-side pagination (API doesn't support server-side pagination)

        Args:
            skip: Number of items to skip
            limit: Maximum items to return
            filter_text: Optional filter text for name/targets

        Returns:
            Tuple of (scans list for current page, total count after filtering)
        """
        try:
            # Fetch all scans (no server-side pagination available)
            scans = [scan async for scan in self._async_client.get_scans()]

            # Apply client-side filter if any
            if filter_text:
                filter_lower = filter_text.lower()
                scans = [
                    s for s in scans
                    if filter_lower in getattr(s, 'name', '').lower()
                    or filter_lower in ' '.join(getattr(s, 'targets', [])).lower()
                ]

            total = len(scans)
            # Apply pagination
            paginated = scans[skip:skip + limit]
            log.debug(f"Fetched {len(paginated)} scans (skip={skip}, limit={limit}, total={total})")
            return paginated, total
        except BBOTServerUnauthorizedError:
            raise
        except BBOTServerError as e:
            log.error(f"Error fetching scans: {e}")
            return [], 0

    async def get_technologies_paginated(
        self,
        skip: int = 0,
        limit: int = 25,
        filter_text: Optional[str] = None,
        **filters
    ) -> tuple[List[Any], int]:
        """
        Fetch technologies with client-side pagination (API doesn't support server-side pagination)

        Args:
            skip: Number of items to skip
            limit: Maximum items to return
            filter_text: Optional filter text for technology/host/domain
            **filters: Additional filters (domain, host, technology, target_id)

        Returns:
            Tuple of (technologies list for current page, total count after filtering)
        """
        try:
            kwargs = {k: v for k, v in filters.items() if v is not None}

            # Fetch all technologies (no server-side pagination available)
            technologies = [tech async for tech in self._async_client.list_technologies(**kwargs)]

            # Apply client-side text filter if any
            if filter_text:
                filter_lower = filter_text.lower()
                technologies = [
                    t for t in technologies
                    if filter_lower in getattr(t, 'technology', '').lower()
                    or filter_lower in getattr(t, 'host', '').lower()
                    or filter_lower in getattr(t, 'domain', '').lower()
                ]

            total = len(technologies)
            # Apply pagination
            paginated = technologies[skip:skip + limit]
            log.debug(f"Fetched {len(paginated)} technologies (skip={skip}, limit={limit}, total={total})")
            return paginated, total
        except BBOTServerError as e:
            log.error(f"Error fetching technologies: {e}")
            return [], 0

    async def get_targets_paginated(
        self,
        skip: int = 0,
        limit: int = 25,
        filter_text: Optional[str] = None
    ) -> tuple[List[Any], int]:
        """
        Fetch targets with client-side pagination (API doesn't support server-side pagination)

        Args:
            skip: Number of items to skip
            limit: Maximum items to return
            filter_text: Optional filter text for name/description

        Returns:
            Tuple of (targets list for current page, total count after filtering)
        """
        try:
            # Fetch all targets (no server-side pagination available)
            targets = await self._async_client.get_targets()

            # Apply client-side filter if any
            if filter_text:
                filter_lower = filter_text.lower()
                targets = [
                    t for t in targets
                    if filter_lower in getattr(t, 'name', '').lower()
                    or filter_lower in getattr(t, 'description', '').lower()
                ]

            total = len(targets)
            # Apply pagination
            paginated = targets[skip:skip + limit]
            log.debug(f"Fetched {len(paginated)} targets (skip={skip}, limit={limit}, total={total})")
            return paginated, total
        except BBOTServerError as e:
            log.error(f"Error fetching targets: {e}")
            return [], 0

    async def create_target(self, name: str, description: str = "", target: Optional[List[str]] = None,
                           seeds: Optional[List[str]] = None, blacklist: Optional[List[str]] = None,
                           strict_dns_scope: bool = False) -> Optional[Any]:
        """
        Create a new target

        Args:
            name: Target name
            description: Target description
            target: List of targets (domains, IPs, CIDRs, URLs)
            seeds: List of seeds (defaults to target if not provided)
            blacklist: List of blacklisted items
            strict_dns_scope: Whether to use strict DNS scope

        Returns:
            Created Target model or None on error
        """
        try:
            # Import CreateTarget model and FastAPI encoder

            # Debug: Log input parameters
            log.info(f"create_target called with: name={name!r}, description={description!r}")
            log.info(f"create_target: target={target}, seeds={seeds}")

            # If seeds not provided, use target as seeds (BBOT core requires seeds)
            if seeds is None and target:
                seeds = target

            # Prepare the data as a dict (exclude None values)
            target_data = {
                "name": name,
                "description": description,
                "target": target if target else [],
                "blacklist": blacklist if blacklist else [],
                "strict_dns_scope": strict_dns_scope,
            }

            # Only add seeds if provided (don't send None)
            if seeds is not None:
                target_data["seeds"] = seeds

            # Debug: Log the data dict
            log.info(f"Target data dict: {target_data}")

            # Create via HTTP client - pass as keyword argument matching API signature
            created_target = await self._async_client.create_target(target=target_data)
            log.info(f"Created target: {name}, returned: {created_target.name if created_target else 'None'}")
            return created_target
        except BBOTServerError as e:
            log.error(f"Error creating target: {e}")
            raise
