async def subdomains_test(self):
    # Insert test data
    for event in self.scan1_events:
        await self.io.create_event(event)

    # Test get_subdomains() method
    subdomains = await self.io.get_subdomains()
    assert set(subdomains) == {
        "asdf.blacklanternsecurity.com",
        "blacklanternsecurity.com",
        "www.blacklanternsecurity.com",
    }

    # insert scan2 events
    for event in self.scan2_events:
        await self.io.create_event(event)

    # Test get_subdomains() after second scan
    subdomains = await self.io.get_subdomains()
    assert set(subdomains) == {
        "asdf.blacklanternsecurity.com",
        "blacklanternsecurity.com",
        "www.blacklanternsecurity.com",
        "api.blacklanternsecurity.com",
    }

    # Test get_subdomains() method with in_scope_only=False
    all_subdomains = await self.io.get_subdomains(in_scope_only=False)
    assert set(all_subdomains) == set(subdomains)  # Assuming all subdomains are in-scope in this test data

    # Test get_subdomain_summary() method
    subdomain_summary = await self.io.get_subdomain_summary()
    assert subdomain_summary == {
        "api.blacklanternsecurity.com": {"DNS_NAME": 1, "DNS_NAME_UNRESOLVED": 1},
        "asdf.blacklanternsecurity.com": {"DNS_NAME": 1, "DNS_NAME_UNRESOLVED": 1},
        "blacklanternsecurity.com": {
            "DNS_NAME": 4,
            "HTTP_RESPONSE": 2,
            "OPEN_TCP_PORT": 2,
            "URL": 2,
            "URL_UNVERIFIED": 2,
        },
        "www.blacklanternsecurity.com": {"DNS_NAME": 2},
    }
