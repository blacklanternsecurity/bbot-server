"""
State service for BBOT Server TUI

Manages shared application state and provides reactive updates.
"""


class StateService:
    """Service for managing shared application state"""

    def __init__(self):
        """Initialize the state service"""
        self.scans = {}
        self.assets = {}
        self.findings = {}
        self.activities = []

    def update_scan(self, scan):
        """Update or add a scan to state"""
        self.scans[scan.id] = scan

    def update_asset(self, asset):
        """Update or add an asset to state"""
        self.assets[asset.host] = asset

    def update_finding(self, finding):
        """Update or add a finding to state"""
        self.findings[finding.id] = finding

    def add_activity(self, activity):
        """Add an activity to the history"""
        self.activities.insert(0, activity)
        # Keep only last 1000 activities
        if len(self.activities) > 1000:
            self.activities = self.activities[:1000]
