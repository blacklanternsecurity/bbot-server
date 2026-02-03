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
            bbot_server: BBOTServer HTTP client instance
        """
        self.bbot_server = bbot_server

    async def get_scans(self) -> List[Any]:
        """
        Fetch all scans

        Returns:
            List of Scan models
        """
        try:
            scans = list(self.bbot_server.get_scans())
            log.debug(f"Fetched {len(scans)} scans")
            return scans
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
            scan = self.bbot_server.get_scan(scan_id)
            return scan
        except BBOTServerNotFoundError:
            log.warning(f"Scan not found: {scan_id}")
            return None
        except BBOTServerError as e:
            log.error(f"Error fetching scan {scan_id}: {e}")
            return None

    async def start_scan(self, target_name: str, preset_name: str, scan_name: Optional[str] = None) -> Optional[Any]:
        """
        Start a new scan

        Args:
            target_name: Name of the target
            preset_name: Name of the preset
            scan_name: Optional custom scan name

        Returns:
            Created Scan model or None on error
        """
        try:
            scan = self.bbot_server.start_scan(
                target_name=target_name,
                preset_name=preset_name,
                scan_name=scan_name
            )
            log.info(f"Started scan: {scan.name}")
            return scan
        except BBOTServerError as e:
            log.error(f"Error starting scan: {e}")
            raise

    async def cancel_scan(self, scan_id: str) -> bool:
        """
        Cancel a running scan

        Args:
            scan_id: Scan identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            self.bbot_server.cancel_scan(scan_id)
            log.info(f"Cancelled scan: {scan_id}")
            return True
        except BBOTServerError as e:
            log.error(f"Error cancelling scan {scan_id}: {e}")
            return False

    async def list_assets(self, domain: Optional[str] = None, target_id: Optional[str] = None,
                         in_scope_only: bool = False, limit: int = 1000) -> List[Any]:
        """
        Fetch assets with optional filters

        Args:
            domain: Filter by domain (includes subdomains)
            target_id: Filter by target ID
            in_scope_only: Only return in-scope assets
            limit: Maximum number of assets to return

        Returns:
            List of Asset models
        """
        try:
            kwargs = {}
            if domain:
                kwargs['domain'] = domain
            if target_id:
                kwargs['target_id'] = target_id
            if in_scope_only:
                kwargs['in_scope_only'] = True

            assets = list(self.bbot_server.list_assets(**kwargs))
            log.debug(f"Fetched {len(assets)} assets")
            return assets[:limit]
        except BBOTServerError as e:
            log.error(f"Error fetching assets: {e}")
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
            asset = self.bbot_server.get_asset(host)
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
                           limit: int = 1000) -> List[Any]:
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

            findings = list(self.bbot_server.list_findings(**kwargs))
            log.debug(f"Fetched {len(findings)} findings")
            return findings[:limit]
        except BBOTServerError as e:
            log.error(f"Error fetching findings: {e}")
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

            activities = list(self.bbot_server.list_activities(**kwargs))
            log.debug(f"Fetched {len(activities)} activities")
            return activities[:limit]
        except BBOTServerError as e:
            log.error(f"Error fetching activities: {e}")
            return []

    async def get_agents(self) -> List[Any]:
        """
        Fetch all agents

        Returns:
            List of Agent models
        """
        try:
            agents = list(self.bbot_server.get_agents())
            log.debug(f"Fetched {len(agents)} agents")
            return agents
        except BBOTServerError as e:
            log.error(f"Error fetching agents: {e}")
            return []

    async def create_agent(self, name: str, description: str = "") -> Optional[Any]:
        """
        Create a new agent

        Args:
            name: Name for the new agent
            description: Optional description

        Returns:
            Created Agent model or None on error
        """
        try:
            agent = self.bbot_server.create_agent(name=name, description=description)
            log.info(f"Created agent: {agent.id}")
            return agent
        except BBOTServerError as e:
            log.error(f"Error creating agent: {e}")
            raise

    async def delete_agent(self, agent_id: str) -> bool:
        """
        Delete an agent

        Args:
            agent_id: Agent identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            self.bbot_server.delete_agent(agent_id)
            log.info(f"Deleted agent: {agent_id}")
            return True
        except BBOTServerError as e:
            log.error(f"Error deleting agent {agent_id}: {e}")
            return False

    async def get_stats(self) -> dict:
        """
        Fetch aggregate statistics

        Returns:
            Dictionary with stats (scan_count, asset_count, finding_count, etc.)
        """
        try:
            stats = self.bbot_server.get_stats()
            log.debug(f"Fetched stats: {stats}")
            return stats
        except BBOTServerError as e:
            log.error(f"Error fetching stats: {e}")
            return {
                'scan_count': 0,
                'active_scan_count': 0,
                'asset_count': 0,
                'finding_count': 0,
                'agent_count': 0,
            }

    async def get_targets(self) -> List[Any]:
        """
        Fetch all targets

        Returns:
            List of Target models
        """
        try:
            targets = list(self.bbot_server.get_targets())
            log.debug(f"Fetched {len(targets)} targets")
            return targets
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
            presets = list(self.bbot_server.get_presets())
            log.debug(f"Fetched {len(presets)} presets")
            return presets
        except BBOTServerError as e:
            log.error(f"Error fetching presets: {e}")
            return []
