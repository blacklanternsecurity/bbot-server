import pytest
from tests.test_applets.base import BaseAppletTest

pytestmark = pytest.mark.skip(reason="Module shelved in Postgres migration")


class TestAppletDNSLinks(BaseAppletTest):
    needs_watchdog = True

    async def after_scan_1(self):
        activities = [a for a in self.asset_messages if a.type in ["NEW_DNS_LINK", "DELETED_DNS_LINK"]]
        new_dns_links = [a for a in activities if a.type == "NEW_DNS_LINK"]
        deleted_dns_links = [a for a in activities if a.type == "DELETED_DNS_LINK"]
        assert len(new_dns_links) > 10
        # we shouldn't have any deleted links yet
        assert len(deleted_dns_links) == 0
        activity_descriptions = [a.description for a in activities]
        assert "New DNS link: evilcorp.com -(TXT)-> [api.evilcorp.com]" in activity_descriptions
        assert "New DNS link: www.evilcorp.com -(A)-> [5.6.7.8]" in activity_descriptions
        assert "New DNS link: www.evilcorp.com -(A)-> [1.2.3.4]" in activity_descriptions
        assert "New DNS link: cname.evilcorp.com -(CNAME)-> [evilcorp.azure.com]" in activity_descriptions

    async def after_scan_2(self):
        activities = [a for a in self.asset_messages if a.type in ["NEW_DNS_LINK", "DELETED_DNS_LINK"]]
        new_dns_links = [a for a in activities if a.type == "NEW_DNS_LINK"]
        deleted_dns_links = [a for a in activities if a.type == "DELETED_DNS_LINK"]
        assert len(new_dns_links) > 10
        # we should have two deleted links
        assert len(deleted_dns_links) == 2
        activity_descriptions = [a.description for a in activities]
        assert "DNS link removed: localhost.evilcorp.com -(A)-> [127.0.0.1]" in activity_descriptions
        assert "New DNS link: localhost.evilcorp.com -(A)-> [127.0.0.2]" in activity_descriptions
        assert "DNS link removed: cname.evilcorp.com -(CNAME)-> [evilcorp.azure.com]" in activity_descriptions
        assert "New DNS link: cname.evilcorp.com -(CNAME)-> [evilcorp.amazonaws.com]" in activity_descriptions
